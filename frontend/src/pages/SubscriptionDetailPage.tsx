import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { getReminderRules, getSubscription, listAuditLogs, listPayments, recordPayment, saveReminderRules, setSubscriptionArchived, transitionSubscription, upcomingEvents, updateServiceDates, updateSubscription, type EventItem, type ServiceDates, type Subscription } from "../api/business";
import { EmptyState, ErrorState, LoadingState } from "../components/AsyncState";
import { Money } from "../components/Money";
import { useOffline } from "../offline/OfflineProvider";

export function SubscriptionDetailPage() {
  const { subscriptionId = "" } = useParams();
  const { offline } = useOffline();
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const [dialog, setDialog] = useState<"edit" | "payment" | "rules" | "dates" | "cancel" | "resume" | null>(null);
  const subscription = useQuery({ queryKey: ["subscription", subscriptionId], queryFn: ({ signal }) => getSubscription(subscriptionId, signal), enabled: Boolean(subscriptionId) });
  const payments = useQuery({ queryKey: ["payments", subscriptionId], queryFn: ({ signal }) => listPayments(subscriptionId, signal), enabled: Boolean(subscriptionId) });
  const rules = useQuery({ queryKey: ["rules", subscriptionId], queryFn: ({ signal }) => getReminderRules(subscriptionId, signal), enabled: Boolean(subscriptionId) });
  const audit = useQuery({ queryKey: ["audit"], queryFn: ({ signal }) => listAuditLogs(signal) });
  const events = useQuery({ queryKey: ["events", 366], queryFn: ({ signal }) => upcomingEvents(366, signal) });
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
  const edit = useMutation({ mutationFn: (changes: { amount: string; next_billing_date: string; auto_renew: boolean }) => updateSubscription(subscription.data as Subscription, changes), onSuccess: refresh });
  const payment = useMutation({ mutationFn: (payload: { amount: string; currency: string; paid_at: string; notes?: string; billing_event_id?: string; advance_schedule: boolean }) => recordPayment(subscriptionId, payload), onSuccess: async () => { await queryClient.invalidateQueries({ queryKey: ["payments", subscriptionId] }); await refresh(); } });
  const reminder = useMutation({ mutationFn: (offsets: number[]) => saveReminderRules(subscriptionId, offsets), onSuccess: async () => { await queryClient.invalidateQueries({ queryKey: ["rules", subscriptionId] }); await refresh(); } });
  const dates = useMutation({ mutationFn: (values: ServiceDates) => updateServiceDates(subscription.data as Subscription, values), onSuccess: refresh });
  const transition = useMutation({ mutationFn: (payload: { target_status: "pending_cancel" | "active"; reason: string; service_expiry_date?: string }) => transitionSubscription(subscription.data as Subscription, payload), onSuccess: refresh });
  const archive = useMutation({ mutationFn: (archived: boolean) => setSubscriptionArchived(subscriptionId, archived), onSuccess: async (_, archived) => { await refresh(); if (archived) void navigate("/subscriptions"); } });
  if (subscription.isPending || payments.isPending || rules.isPending || audit.isPending) return <LoadingState label="正在读取订阅详情…" />;
  const firstError = subscription.error ?? payments.error ?? rules.error ?? audit.error;
  if (firstError || !subscription.data) return <ErrorState error={firstError} />;
  const item = subscription.data;
  const currentBillingEvent = events.data?.find((event) => event.subscription_id === item.id && event.event_type === "billing" && event.status === "planned" && event.event_date === item.billing_plan?.next_billing_date);
  const logs = audit.data?.items.filter((entry) => entry.entity_id === item.id || (entry.entity_type === "payment" && payments.data?.some((payment) => payment.id === entry.entity_id))).slice(0, 8) ?? [];
  return <section>
    <div className="detail-breadcrumb"><Link to="/subscriptions">← 所有订阅</Link></div>
    <header className="detail-hero"><div className="service-mark hero-mark">{item.name.slice(0, 1).toUpperCase()}</div><div><div className="title-line"><h1>{item.name}</h1><span className={`status-pill ${item.archived_at ? "archived" : item.status}`}>{item.archived_at ? "已归档" : item.status}</span></div><p className="muted">{item.vendor || "未填写供应商"}</p></div><div className="detail-actions"><button className="secondary-button" disabled={offline} onClick={() => setDialog("edit")}>编辑计划</button><button className="primary-button" disabled={offline} onClick={() => setDialog("payment")}>＋ 记录付款</button>{item.status === "pending_cancel" ? <button className="secondary-button" disabled={offline} onClick={() => setDialog("resume")}>撤销取消</button> : ["active", "trial", "paused"].includes(item.status) ? <button className="danger-button" disabled={offline} onClick={() => setDialog("cancel")}>计划取消</button> : null}<button className={item.archived_at ? "secondary-button" : "danger-button"} disabled={offline || archive.isPending} onClick={() => { if (item.archived_at || window.confirm("归档后将从默认列表隐藏，之后仍可恢复。确认归档？")) archive.mutate(!item.archived_at); }}>{item.archived_at ? "恢复" : "归档"}</button></div></header>
    <div className="detail-grid"><div className="detail-main">
      <section className="panel"><div className="panel-heading"><div><p className="eyebrow">Billing</p><h2>计费计划</h2></div></div>{item.billing_plan ? <div className="definition-grid"><div><span>价格</span><strong><Money amount={item.billing_plan.amount} currency={item.billing_plan.currency} /></strong></div><div><span>周期</span><strong>每 {item.billing_plan.interval_count} {item.billing_plan.interval_unit}</strong></div><div><span>{item.billing_plan.auto_renew ? "下次续费" : "续费安排"}</span><strong>{item.billing_plan.auto_renew ? item.billing_plan.next_billing_date ?? "—" : "不自动续费"}</strong></div><div><span>自动续费</span><strong>{item.billing_plan.auto_renew ? "已开启" : "已关闭"}</strong></div></div> : <EmptyState title="没有计费计划" message="无法显示价格和续费日期。" />}</section>
      <section className="panel"><div className="panel-heading"><div><p className="eyebrow">Payments</p><h2>付款记录</h2></div><button className="text-button" onClick={() => setDialog("payment")}>添加</button></div>{payments.data?.length ? <div className="payment-list">{payments.data.map((entry) => <article key={entry.id}><div><strong><Money amount={entry.amount} currency={entry.currency} /></strong><span>{new Intl.DateTimeFormat("zh-CN", { dateStyle: "medium", timeStyle: "short" }).format(new Date(entry.paid_at))}</span></div><span>{entry.source}</span></article>)}</div> : <EmptyState title="尚无付款" message="记录实际付款后，统计会与预计金额分开展示。" />}</section>
    </div><aside className="detail-side">
      <section className="panel"><div className="panel-heading"><div><p className="eyebrow">Reminders</p><h2>提醒</h2></div><button className="text-button" disabled={offline} onClick={() => setDialog("rules")}>编辑</button></div>{rules.data?.filter((rule) => rule.enabled).length ? <div className="rule-list">{rules.data.filter((rule) => rule.enabled).map((rule) => <span key={rule.id}>提前 {rule.offset_days} 天 · {rule.event_type}</span>)}</div> : <p className="muted">尚未配置提醒。</p>}</section>
      <section className="panel"><div className="panel-heading"><div><p className="eyebrow">Dates</p><h2>关键日期</h2></div><button className="text-button" disabled={offline} onClick={() => setDialog("dates")}>编辑</button></div><div className="date-list"><span><small>试用结束</small>{item.service_dates?.trial_end_date ?? "—"}</span><span><small>服务到期</small>{item.service_dates?.service_expiry_date ?? "—"}</span><span><small>取消截止</small>{item.service_dates?.cancellation_deadline ?? "—"}</span><span><small>合同结束</small>{item.service_dates?.contract_end_date ?? "—"}</span></div></section>
      <section className="panel"><div className="panel-heading"><div><p className="eyebrow">Audit</p><h2>最近活动</h2></div></div>{logs.length ? <div className="audit-list">{logs.map((entry) => <article key={entry.id}><span>{entry.action}</span><small>{entry.actor_type} · {new Intl.DateTimeFormat("zh-CN", { dateStyle: "short", timeStyle: "short" }).format(new Date(entry.occurred_at))}</small></article>)}</div> : <p className="muted">暂无活动记录。</p>}</section>
    </aside></div>
    {dialog === "edit" && item.billing_plan && <EditDialog item={item} pending={edit.isPending} error={edit.error} onClose={() => setDialog(null)} onSubmit={(values) => edit.mutate(values)} />}
    {dialog === "payment" && item.billing_plan && <PaymentDialog currency={item.billing_plan.currency} amount={item.billing_plan.amount} event={currentBillingEvent} autoRenew={item.billing_plan.auto_renew} pending={payment.isPending} error={payment.error} onClose={() => setDialog(null)} onSubmit={(values) => payment.mutate(values)} />}
    {dialog === "rules" && <RulesDialog initial={rules.data?.filter((rule) => rule.enabled).map((rule) => rule.offset_days) ?? []} pending={reminder.isPending} error={reminder.error} onClose={() => setDialog(null)} onSubmit={(values) => reminder.mutate(values)} />}
    {dialog === "dates" && <DatesDialog initial={item.service_dates} pending={dates.isPending} error={dates.error} onClose={() => setDialog(null)} onSubmit={(values) => dates.mutate(values)} />}
    {dialog === "cancel" && <TransitionDialog mode="cancel" initialExpiry={item.service_dates?.service_expiry_date} pending={transition.isPending} error={transition.error} onClose={() => setDialog(null)} onSubmit={(payload) => transition.mutate(payload)} />}
    {dialog === "resume" && <TransitionDialog mode="resume" pending={transition.isPending} error={transition.error} onClose={() => setDialog(null)} onSubmit={(payload) => transition.mutate(payload)} />}
  </section>;
}

function field(data: FormData, name: string) { const value = data.get(name); return typeof value === "string" ? value : ""; }

function DialogFrame({ title, pending, error, onClose, onSubmit, children, submitLabel }: { title: string; pending: boolean; error: unknown; onClose: () => void; onSubmit: (data: FormData) => void; children: React.ReactNode; submitLabel: string }) {
  function submit(event: FormEvent<HTMLFormElement>) { event.preventDefault(); onSubmit(new FormData(event.currentTarget)); }
  return <div className="modal-backdrop"><section className="modal" role="dialog" aria-modal="true" aria-label={title}><div className="panel-heading"><h2>{title}</h2><button className="icon-button" onClick={onClose} aria-label="关闭">×</button></div><form onSubmit={submit}>{children}{error ? <ErrorState error={error} /> : null}<div className="modal-actions"><button type="button" className="secondary-button" onClick={onClose}>取消</button><button className="primary-button" disabled={pending} type="submit">{pending ? "正在保存…" : submitLabel}</button></div></form></section></div>;
}

function EditDialog({ item, pending, error, onClose, onSubmit }: { item: Subscription; pending: boolean; error: unknown; onClose: () => void; onSubmit: (value: { amount: string; next_billing_date: string; auto_renew: boolean }) => void }) {
  return <DialogFrame title="编辑计费计划" pending={pending} error={error} onClose={onClose} submitLabel="保存更改" onSubmit={(data) => onSubmit({ amount: field(data, "amount"), next_billing_date: field(data, "next_billing_date"), auto_renew: data.get("auto_renew") === "on" })}><div className="form-grid"><label>金额<input name="amount" type="number" min="0" step="0.01" required defaultValue={item.billing_plan?.amount} /></label><label>下次续费<input name="next_billing_date" type="date" required defaultValue={item.billing_plan?.next_billing_date ?? ""} /></label><label className="cache-toggle"><input name="auto_renew" type="checkbox" defaultChecked={item.billing_plan?.auto_renew} />到期后继续自动续费</label></div></DialogFrame>;
}

function PaymentDialog({ currency, amount, event, autoRenew, pending, error, onClose, onSubmit }: { currency: string; amount: string; event?: EventItem; autoRenew: boolean; pending: boolean; error: unknown; onClose: () => void; onSubmit: (value: { amount: string; currency: string; paid_at: string; notes?: string; billing_event_id?: string; advance_schedule: boolean }) => void }) {
  const now = new Date(); now.setMinutes(now.getMinutes() - now.getTimezoneOffset());
  return <DialogFrame title="记录实际付款" pending={pending} error={error} onClose={onClose} submitLabel="记录付款" onSubmit={(data) => { const advance_schedule = data.get("advance_schedule") === "on"; onSubmit({ amount: field(data, "amount"), currency, paid_at: new Date(field(data, "paid_at")).toISOString(), notes: field(data, "notes"), billing_event_id: advance_schedule ? event?.id : undefined, advance_schedule }); }}><div className="form-grid"><label>金额<input name="amount" type="number" min="0.01" step="0.01" required defaultValue={amount} /></label><label>币种<input value={currency} disabled /></label><label>付款时间<input name="paid_at" type="datetime-local" required defaultValue={now.toISOString().slice(0, 16)} /></label><label>备注<input name="notes" maxLength={500} /></label><label className="cache-toggle"><input name="advance_schedule" type="checkbox" defaultChecked={autoRenew && Boolean(event)} disabled={!event} />推进到下一账期</label></div>{event ? <p className="muted">关联当前账单事件：{event.event_date}</p> : <p className="muted">没有匹配的当前账单事件，本次付款将作为历史补录且不推进账期。</p>}</DialogFrame>;
}

function RulesDialog({ initial, pending, error, onClose, onSubmit }: { initial: number[]; pending: boolean; error: unknown; onClose: () => void; onSubmit: (value: number[]) => void }) {
  return <DialogFrame title="续费提醒" pending={pending} error={error} onClose={onClose} submitLabel="保存提醒" onSubmit={(data) => onSubmit([...new Set([field(data, "first"), field(data, "second")].filter(Boolean).map(Number))])}><p className="muted">最多配置两条外部提醒；系统负责到期计算和去重，由 Hermes 或其他授权消费者完成通知。</p><div className="form-grid"><label>第一条（提前天数）<input name="first" type="number" min="0" max="3650" defaultValue={initial[0] ?? 5} /></label><label>第二条（提前天数）<input name="second" type="number" min="0" max="3650" defaultValue={initial[1] ?? 1} /></label></div></DialogFrame>;
}

function DatesDialog({ initial, pending, error, onClose, onSubmit }: { initial?: ServiceDates; pending: boolean; error: unknown; onClose: () => void; onSubmit: (value: ServiceDates) => void }) {
  const nullableDate = (data: FormData, name: string) => field(data, name) || null;
  return <DialogFrame title="编辑关键日期" pending={pending} error={error} onClose={onClose} submitLabel="保存日期" onSubmit={(data) => onSubmit({ trial_end_date: nullableDate(data, "trial_end_date"), service_expiry_date: nullableDate(data, "service_expiry_date"), cancellation_deadline: nullableDate(data, "cancellation_deadline"), contract_end_date: nullableDate(data, "contract_end_date") })}><p className="muted">留空可清除日期；保存后对应的未来事件会同步更新。</p><div className="form-grid"><label>试用结束<input name="trial_end_date" type="date" defaultValue={initial?.trial_end_date ?? ""} /></label><label>服务到期<input name="service_expiry_date" type="date" defaultValue={initial?.service_expiry_date ?? ""} /></label><label>取消截止<input name="cancellation_deadline" type="date" defaultValue={initial?.cancellation_deadline ?? ""} /></label><label>合同结束<input name="contract_end_date" type="date" defaultValue={initial?.contract_end_date ?? ""} /></label></div></DialogFrame>;
}

function TransitionDialog({ mode, initialExpiry, pending, error, onClose, onSubmit }: { mode: "cancel" | "resume"; initialExpiry?: string | null; pending: boolean; error: unknown; onClose: () => void; onSubmit: (value: { target_status: "pending_cancel" | "active"; reason: string; service_expiry_date?: string }) => void }) {
  const cancelling = mode === "cancel";
  return <DialogFrame title={cancelling ? "计划取消订阅" : "撤销取消计划"} pending={pending} error={error} onClose={onClose} submitLabel={cancelling ? "确认计划取消" : "确认撤销"} onSubmit={(data) => onSubmit({ target_status: cancelling ? "pending_cancel" : "active", reason: field(data, "reason"), ...(cancelling ? { service_expiry_date: field(data, "service_expiry_date") } : {}) })}><p className="muted">{cancelling ? "这里只记录服务到期安排并停止生成后续账单；仍需自行在服务商处完成取消。" : "撤销后将恢复自动续费，并重新生成后续账单事件。"}</p><div className="form-grid">{cancelling && <label>服务到期<input name="service_expiry_date" type="date" required defaultValue={initialExpiry ?? ""} /></label>}<label>原因<input name="reason" required maxLength={500} /></label></div></DialogFrame>;
}
