import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { analyticsSummary, listSubscriptions, upcomingEvents } from "../api/business";
import { EmptyState, ErrorState, LoadingState } from "../components/AsyncState";
import { Money } from "../components/Money";

const eventLabels: Record<string, string> = { billing: "续费", expiry: "到期", trial_end: "试用结束", cancellation_deadline: "取消截止", contract_end: "合同结束" };

export function DashboardPage() {
  const analytics = useQuery({ queryKey: ["analytics"], queryFn: ({ signal }) => analyticsSummary(signal) });
  const subscriptions = useQuery({ queryKey: ["subscriptions", "dashboard"], queryFn: ({ signal }) => listSubscriptions("", signal) });
  const events = useQuery({ queryKey: ["events", 30], queryFn: ({ signal }) => upcomingEvents(30, signal) });
  const firstError = analytics.error ?? subscriptions.error ?? events.error;
  if (analytics.isPending || subscriptions.isPending || events.isPending) return <LoadingState label="正在整理工作区…" />;
  if (firstError) return <ErrorState error={firstError} />;
  const expected = Object.entries(analytics.data?.expected ?? {});
  const actual = Object.entries(analytics.data?.actual ?? {});
  const names = new Map(subscriptions.data?.items.map((item) => [item.id, item.name]));
  return (
    <section>
      <header className="page-header"><div><p className="eyebrow">Dashboard</p><h1>今天，一切按计划。</h1><p className="muted">未来 30 天有 {events.data?.length ?? 0} 个关键事件。</p></div><Link className="primary-button link-button" to="/subscriptions?create=1">＋ 新建订阅</Link></header>
      <div className="metric-grid">
        <article className="metric-card"><span>活跃订阅</span><strong>{subscriptions.data?.items.filter((item) => item.status === "active").length ?? 0}</strong><small>共 {subscriptions.data?.total ?? 0} 项</small></article>
        <article className="metric-card"><span>预计支出</span><div className="money-stack">{expected.length ? expected.map(([currency, amount]) => <strong key={currency}><Money amount={amount} currency={currency} /></strong>) : <strong>—</strong>}</div><small>未来已生成账单事件</small></article>
        <article className="metric-card"><span>实际支出</span><div className="money-stack">{actual.length ? actual.map(([currency, amount]) => <strong key={currency}><Money amount={amount} currency={currency} /></strong>) : <strong>—</strong>}</div><small>已记录付款</small></article>
      </div>
      <div className="dashboard-grid">
        <section className="panel"><div className="panel-heading"><div><p className="eyebrow">Timeline</p><h2>即将发生</h2></div><Link to="/events">查看全部</Link></div>{events.data?.length ? <div className="event-list">{events.data.slice(0, 6).map((event) => <article key={event.id}><time>{new Intl.DateTimeFormat("zh-CN", { month: "short", day: "numeric" }).format(new Date(`${event.event_date}T00:00:00`))}</time><div><strong>{names.get(event.subscription_id) ?? "订阅"}</strong><span>{eventLabels[event.event_type] ?? event.event_type}</span></div>{event.amount && event.currency && <Money amount={event.amount} currency={event.currency} />}</article>)}</div> : <EmptyState title="未来很安静" message="未来 30 天没有账单或服务期限事件。" />}</section>
        <section className="panel"><div className="panel-heading"><div><p className="eyebrow">Portfolio</p><h2>最近订阅</h2></div><Link to="/subscriptions">管理</Link></div>{subscriptions.data?.items.length ? <div className="mini-subscriptions">{subscriptions.data.items.slice(0, 5).map((item) => <Link key={item.id} to={`/subscriptions/${item.id}`}><span className="service-mark">{item.name.slice(0, 1).toUpperCase()}</span><span><strong>{item.name}</strong><small>{item.billing_plan ? `${item.billing_plan.currency} · ${item.billing_plan.next_billing_date ?? "无续费日"}` : "无计费计划"}</small></span><span className={`status-pill ${item.status}`}>{item.status}</span></Link>)}</div> : <EmptyState title="还没有订阅" message="创建第一项订阅后，它会出现在这里。" />}</section>
      </div>
    </section>
  );
}
