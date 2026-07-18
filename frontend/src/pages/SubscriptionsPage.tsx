import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState, type FormEvent } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { createSubscription, listSubscriptions, type SubscriptionCreate } from "../api/business";
import { EmptyState, ErrorState, LoadingState } from "../components/AsyncState";
import { Money } from "../components/Money";

export function SubscriptionsPage() {
  const queryClient = useQueryClient();
  const [params, setParams] = useSearchParams();
  const [query, setQuery] = useState("");
  const [layout, setLayout] = useState<"cards" | "table">("cards");
  const [includeArchived, setIncludeArchived] = useState(false);
  const [open, setOpen] = useState(params.get("create") === "1");
  useEffect(() => setOpen(params.get("create") === "1"), [params]);
  const subscriptions = useQuery({ queryKey: ["subscriptions", query, includeArchived], queryFn: ({ signal }) => listSubscriptions(query, signal, includeArchived) });
  const mutation = useMutation({ mutationFn: createSubscription, onSuccess: async () => { await queryClient.invalidateQueries({ queryKey: ["subscriptions"] }); await queryClient.invalidateQueries({ queryKey: ["analytics"] }); setOpen(false); setParams({}); } });
  return (
    <section>
      <header className="page-header"><div><p className="eyebrow">Subscriptions</p><h1>订阅</h1><p className="muted">管理价格、续费日期和服务状态。</p></div><button className="primary-button" onClick={() => { setOpen(true); setParams({ create: "1" }); }}>＋ 新建订阅</button></header>
      <div className="toolbar"><label className="search-field"><span aria-hidden="true">⌕</span><input aria-label="搜索订阅" placeholder="搜索名称或供应商" value={query} onChange={(event) => setQuery(event.target.value)} /></label><label className="archive-toggle"><input type="checkbox" checked={includeArchived} onChange={(event) => setIncludeArchived(event.target.checked)} />显示已归档</label><div className="segmented" aria-label="布局"><button className={layout === "cards" ? "active" : ""} onClick={() => setLayout("cards")} aria-label="卡片视图">▦</button><button className={layout === "table" ? "active" : ""} onClick={() => setLayout("table")} aria-label="表格视图">☷</button></div></div>
      {subscriptions.isPending ? <LoadingState /> : subscriptions.error ? <ErrorState error={subscriptions.error} /> : subscriptions.data.items.length === 0 ? <EmptyState title={query ? "没有匹配结果" : "还没有订阅"} message={query ? "试试其他关键词。" : "创建第一项订阅，开始跟踪续费与支出。"} /> : layout === "cards" ? <div className="subscription-grid">{subscriptions.data.items.map((item) => <Link className={`subscription-card ${item.archived_at ? "archived" : ""}`} key={item.id} to={`/subscriptions/${item.id}`}><div className="card-top"><span className="service-mark large">{item.name.slice(0, 1).toUpperCase()}</span><span className={`status-pill ${item.archived_at ? "archived" : item.status}`}>{item.archived_at ? "已归档" : item.status}</span></div><div><h2>{item.name}</h2><p>{item.vendor || "未填写供应商"}</p></div>{item.billing_plan && <div className="card-money"><strong><Money amount={item.billing_plan.amount} currency={item.billing_plan.currency} /></strong><span>下次续费 {item.billing_plan.next_billing_date ?? "—"}</span></div>}</Link>)}</div> : <div className="table-wrap"><table><thead><tr><th>订阅</th><th>状态</th><th>价格</th><th>下次续费</th></tr></thead><tbody>{subscriptions.data.items.map((item) => <tr key={item.id}><td><Link to={`/subscriptions/${item.id}`}>{item.name}</Link><small>{item.vendor}</small></td><td><span className={`status-pill ${item.archived_at ? "archived" : item.status}`}>{item.archived_at ? "已归档" : item.status}</span></td><td>{item.billing_plan ? <Money amount={item.billing_plan.amount} currency={item.billing_plan.currency} /> : "—"}</td><td>{item.billing_plan?.next_billing_date ?? "—"}</td></tr>)}</tbody></table></div>}
      {open && <SubscriptionDialog pending={mutation.isPending} error={mutation.error} onClose={() => { setOpen(false); setParams({}); }} onSubmit={(payload) => mutation.mutate(payload)} />}
    </section>
  );
}

function SubscriptionDialog({ pending, error, onClose, onSubmit }: { pending: boolean; error: unknown; onClose: () => void; onSubmit: (payload: SubscriptionCreate) => void }) {
  const today = new Date().toISOString().slice(0, 10);
  const value = (data: FormData, name: string) => {
    const entry = data.get(name);
    return typeof entry === "string" ? entry : "";
  };
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const nextBillingDate = value(data, "next_billing_date");
    onSubmit({ name: value(data, "name"), vendor: value(data, "vendor"), status: "active", billing_plan: { amount: value(data, "amount"), currency: value(data, "currency").toUpperCase(), interval_unit: value(data, "interval") as "day" | "week" | "month" | "year", interval_count: 1, anchor_date: nextBillingDate, next_billing_date: nextBillingDate, auto_renew: true, billing_mode: "fixed" } });
  }
  return <div className="modal-backdrop" role="presentation"><section className="modal" role="dialog" aria-modal="true" aria-labelledby="new-subscription"><div className="panel-heading"><div><p className="eyebrow">New subscription</p><h2 id="new-subscription">新建订阅</h2></div><button className="icon-button" onClick={onClose} aria-label="关闭">×</button></div><form onSubmit={submit}><div className="form-grid"><label>名称<input name="name" required maxLength={200} autoFocus /></label><label>供应商<input name="vendor" maxLength={200} /></label><label>金额<input name="amount" required type="number" min="0" step="0.01" /></label><label>币种<input name="currency" defaultValue="USD" required minLength={3} maxLength={3} /></label><label>周期<select name="interval" defaultValue="month"><option value="month">每月</option><option value="year">每年</option><option value="week">每周</option><option value="day">每天</option></select></label><label>下次续费<input name="next_billing_date" type="date" min={today} defaultValue={today} required /></label></div>{error ? <ErrorState error={error} /> : null}<div className="modal-actions"><button className="secondary-button" type="button" onClick={onClose}>取消</button><button className="primary-button" disabled={pending} type="submit">{pending ? "正在创建…" : "创建订阅"}</button></div></form></section></div>;
}
