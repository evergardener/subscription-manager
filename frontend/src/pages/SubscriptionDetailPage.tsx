import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { getReminderRules, getSubscription, listAuditLogs, listPayments, recordPayment, saveReminderRules, setSubscriptionArchived, updateSubscription, type Subscription } from "../api/business";
import { EmptyState, ErrorState, LoadingState } from "../components/AsyncState";
import { Money } from "../components/Money";

export function SubscriptionDetailPage() {
  const { subscriptionId = "" } = useParams();
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const [dialog, setDialog] = useState<"edit" | "payment" | "rules" | null>(null);
  const subscription = useQuery({ queryKey: ["subscription", subscriptionId], queryFn: ({ signal }) => getSubscription(subscriptionId, signal), enabled: Boolean(subscriptionId) });
  const payments = useQuery({ queryKey: ["payments", subscriptionId], queryFn: ({ signal }) => listPayments(subscriptionId, signal), enabled: Boolean(subscriptionId) });
  const rules = useQuery({ queryKey: ["rules", subscriptionId], queryFn: ({ signal }) => getReminderRules(subscriptionId, signal), enabled: Boolean(subscriptionId) });
  const audit = useQuery({ queryKey: ["audit"], queryFn: ({ signal }) => listAuditLogs(signal) });
  const refresh = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["subscription", subscriptionId] }),
      queryClient.invalidateQueries({ queryKey: ["subscriptions"] }),
      queryClient.invalidateQueries({ queryKey: ["events"] }),
      queryClient.invalidateQueries({ queryKey: ["analytics"] }),
      queryClient.invalidateQueries({ queryKey: ["audit"] }),
    ]);
    setDialog(null);
  };
  const edit = useMutation({ mutationFn: (changes: { amount: string; next_billing_date: string }) => updateSubscription(subscription.data as Subscription, changes), onSuccess: refresh });
  const payment = useMutation({ mutationFn: (payload: { amount: string; currency: string; paid_at: string; notes?: string }) => recordPayment(subscriptionId, payload), onSuccess: async () => { await queryClient.invalidateQueries({ queryKey: ["payments", subscriptionId] }); await refresh(); } });
  const reminder = useMutation({ mutationFn: (offsets: number[]) => saveReminderRules(subscriptionId, offsets), onSuccess: async () => { await queryClient.invalidateQueries({ queryKey: ["rules", subscriptionId] }); await refresh(); } });
  const archive = useMutation({ mutationFn: (archived: boolean) => setSubscriptionArchived(subscriptionId, archived), onSuccess: async (_, archived) => { await refresh(); if (archived) void navigate("/subscriptions"); } });
  if (subscription.isPending || payments.isPending || rules.isPending || audit.isPending) return <LoadingState label="正在读取订阅详情…" />;
  const firstError = subscription.error ?? payments.error ?? rules.error ?? audit.error;
  if (firstError || !subscription.data) return <ErrorState error={firstError} />;
  const item = subscription.data;
  const logs = audit.data?.items.filter((entry) => entry.entity_id === item.id || (entry.entity_type === "payment" && payments.data?.some((payment) => payment.id === entry.entity_id))).slice(0, 8) ?? [];
  return <section>
    <div className="detail-breadcrumb"><Link to="/subscriptions">← 所有订阅</Link></div>
    <header className="detail-hero"><div className="service-mark hero-mark">{item.name.slice(0, 1).toUpperCase()}</div><div><div className="title-line"><h1>{item.name}</h1><span className={`status-pill ${item.archived_at ? "archived" : item.status}`}>{item.archived_at ? "已归档" : item.status}</span></div><p className="muted">{item.vendor || "未填写供应商"}</p></div><div className="detail-actions"><button className="secondary-button" onClick={() => setDialog("edit")}>编辑计划</button><button className="primary-button" onClick={() => setDialog("payment")}>＋ 记录付款</button><button className={item.archived_at ? "secondary-button" : "danger-button"} disabled={archive.isPending} onClick={() => { if (item.archived_at || window.confirm("归档后将从默认列表隐藏，之后仍可恢复。确认归档？")) archive.mutate(!item.archived_at); }}>{item.archived_at ? "恢复" : "归档"}</button></div></header>
    <div className="detail-grid"><div className="detail-main">
      <section className="panel"><div className="panel-heading"><div><p className="eyebrow">Billing</p><h2>计费计划</h2></div></div>{item.billing_plan ? <div className="definition-grid"><div><span>价格</span><strong><Money amount={item.billing_plan.amount} currency={item.billing_plan.currency} /></strong></div><div><span>周期</span><strong>每 {item.billing_plan.interval_count} {item.billing_plan.interval_unit}</strong></div><div><span>下次续费</span><strong>{item.billing_plan.next_billing_date ?? "—"}</strong></div><div><span>自动续费</span><strong>{item.billing_plan.auto_renew ? "已开启" : "已关闭"}</strong></div></div> : <EmptyState title="没有计费计划" message="无法显示价格和续费日期。" />}</section>
      <section className="panel"><div className="panel-heading"><div><p className="eyebrow">Payments</p><h2>付款记录</h2></div><button className="text-button" onClick={() => setDialog("payment")}>添加</button></div>{payments.data?.length ? <div className="payment-list">{payments.data.map((entry) => <article key={entry.id}><div><strong><Money amount={entry.amount} currency={entry.currency} /></strong><span>{new Intl.DateTimeFormat("zh-CN", { dateStyle: "medium", timeStyle: "short" }).format(new Date(entry.paid_at))}</span></div><span>{entry.source}</span></article>)}</div> : <EmptyState title="尚无付款" message="记录实际付款后，统计会与预计金额分开展示。" />}</section>
    </div><aside className="detail-side">
      <section className="panel"><div className="panel-heading"><div><p className="eyebrow">Reminders</p><h2>提醒</h2></div><button className="text-button" onClick={() => setDialog("rules")}>编辑</button></div>{rules.data?.filter((rule) => rule.enabled).length ? <div className="rule-list">{rules.data.filter((rule) => rule.enabled).map((rule) => <span key={rule.id}>提前 {rule.offset_days} 天 · {rule.event_type}</span>)}</div> : <p className="muted">尚未配置提醒。</p>}</section>
      <section className="panel"><div className="panel-heading"><div><p className="eyebrow">Dates</p><h2>关键日期</h2></div></div><div className="date-list"><span><small>试用结束</small>{item.service_dates?.trial_end_date ?? "—"}</span><span><small>服务到期</small>{item.service_dates?.service_expiry_date ?? "—"}</span><span><small>取消截止</small>{item.service_dates?.cancellation_deadline ?? "—"}</span></div></section>
      <section className="panel"><div className="panel-heading"><div><p className="eyebrow">Audit</p><h2>最近活动</h2></div></div>{logs.length ? <div className="audit-list">{logs.map((entry) => <article key={entry.id}><span>{entry.action}</span><small>{entry.actor_type} · {new Intl.DateTimeFormat("zh-CN", { dateStyle: "short", timeStyle: "short" }).format(new Date(entry.occurred_at))}</small></article>)}</div> : <p className="muted">暂无活动记录。</p>}</section>
    </aside></div>
    {dialog === "edit" && item.billing_plan && <EditDialog item={item} pending={edit.isPending} error={edit.error} onClose={() => setDialog(null)} onSubmit={(values) => edit.mutate(values)} />}
    {dialog === "payment" && item.billing_plan && <PaymentDialog currency={item.billing_plan.currency} amount={item.billing_plan.amount} pending={payment.isPending} error={payment.error} onClose={() => setDialog(null)} onSubmit={(values) => payment.mutate(values)} />}
    {dialog === "rules" && <RulesDialog initial={rules.data?.filter((rule) => rule.enabled).map((rule) => rule.offset_days) ?? []} pending={reminder.isPending} error={reminder.error} onClose={() => setDialog(null)} onSubmit={(values) => reminder.mutate(values)} />}
  </section>;
}

function field(data: FormData, name: string) { const value = data.get(name); return typeof value === "string" ? value : ""; }

function DialogFrame({ title, pending, error, onClose, onSubmit, children, submitLabel }: { title: string; pending: boolean; error: unknown; onClose: () => void; onSubmit: (data: FormData) => void; children: React.ReactNode; submitLabel: string }) {
  function submit(event: FormEvent<HTMLFormElement>) { event.preventDefault(); onSubmit(new FormData(event.currentTarget)); }
  return <div className="modal-backdrop"><section className="modal" role="dialog" aria-modal="true" aria-label={title}><div className="panel-heading"><h2>{title}</h2><button className="icon-button" onClick={onClose} aria-label="关闭">×</button></div><form onSubmit={submit}>{children}{error ? <ErrorState error={error} /> : null}<div className="modal-actions"><button type="button" className="secondary-button" onClick={onClose}>取消</button><button className="primary-button" disabled={pending} type="submit">{pending ? "正在保存…" : submitLabel}</button></div></form></section></div>;
}

function EditDialog({ item, pending, error, onClose, onSubmit }: { item: Subscription; pending: boolean; error: unknown; onClose: () => void; onSubmit: (value: { amount: string; next_billing_date: string }) => void }) {
  return <DialogFrame title="编辑计费计划" pending={pending} error={error} onClose={onClose} submitLabel="保存更改" onSubmit={(data) => onSubmit({ amount: field(data, "amount"), next_billing_date: field(data, "next_billing_date") })}><div className="form-grid"><label>金额<input name="amount" type="number" min="0" step="0.01" required defaultValue={item.billing_plan?.amount} /></label><label>下次续费<input name="next_billing_date" type="date" required defaultValue={item.billing_plan?.next_billing_date ?? ""} /></label></div></DialogFrame>;
}

function PaymentDialog({ currency, amount, pending, error, onClose, onSubmit }: { currency: string; amount: string; pending: boolean; error: unknown; onClose: () => void; onSubmit: (value: { amount: string; currency: string; paid_at: string; notes?: string }) => void }) {
  const now = new Date(); now.setMinutes(now.getMinutes() - now.getTimezoneOffset());
  return <DialogFrame title="记录实际付款" pending={pending} error={error} onClose={onClose} submitLabel="记录付款" onSubmit={(data) => onSubmit({ amount: field(data, "amount"), currency, paid_at: new Date(field(data, "paid_at")).toISOString(), notes: field(data, "notes") })}><div className="form-grid"><label>金额<input name="amount" type="number" min="0.01" step="0.01" required defaultValue={amount} /></label><label>币种<input value={currency} disabled /></label><label>付款时间<input name="paid_at" type="datetime-local" required defaultValue={now.toISOString().slice(0, 16)} /></label><label>备注<input name="notes" maxLength={500} /></label></div></DialogFrame>;
}

function RulesDialog({ initial, pending, error, onClose, onSubmit }: { initial: number[]; pending: boolean; error: unknown; onClose: () => void; onSubmit: (value: number[]) => void }) {
  return <DialogFrame title="续费提醒" pending={pending} error={error} onClose={onClose} submitLabel="保存提醒" onSubmit={(data) => onSubmit([...new Set([field(data, "first"), field(data, "second")].filter(Boolean).map(Number))])}><p className="muted">最多配置两条 ntfy 续费提醒；重复扫描不会重复投递。</p><div className="form-grid"><label>第一条（提前天数）<input name="first" type="number" min="0" max="3650" defaultValue={initial[0] ?? 5} /></label><label>第二条（提前天数）<input name="second" type="number" min="0" max="3650" defaultValue={initial[1] ?? 1} /></label></div></DialogFrame>;
}
