import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { latestCnyRates, listSubscriptions, upcomingEvents } from "../api/business";
import { EmptyState, ErrorState, LoadingState } from "../components/AsyncState";
import { Money } from "../components/Money";

const eventLabels: Record<string, string> = { billing: "续费", expiry: "到期", trial_end: "试用结束", cancellation_deadline: "取消截止", contract_end: "合同结束" };

export function DashboardPage() {
  const subscriptions = useQuery({ queryKey: ["subscriptions", "dashboard"], queryFn: ({ signal }) => listSubscriptions("", signal) });
  const events = useQuery({ queryKey: ["events", 62], queryFn: ({ signal }) => upcomingEvents(62, signal) });
  const rates = useQuery({ queryKey: ["exchange-rates", "CNY"], queryFn: ({ signal }) => latestCnyRates(signal), staleTime: 6 * 60 * 60 * 1000, retry: 1 });
  const firstError = subscriptions.error ?? events.error;
  if (subscriptions.isPending || events.isPending) return <LoadingState label="正在整理工作区…" />;
  if (firstError) return <ErrorState error={firstError} />;
  const now = new Date();
  const nextMonthStart = new Date(now.getFullYear(), now.getMonth() + 1, 1);
  const followingMonthStart = new Date(now.getFullYear(), now.getMonth() + 2, 1);
  const nextMonthExpected = new Map<string, number>();
  for (const event of events.data ?? []) {
    const eventDate = new Date(`${event.event_date}T00:00:00`);
    if (event.event_type === "billing" && event.amount && event.currency && eventDate >= nextMonthStart && eventDate < followingMonthStart) {
      nextMonthExpected.set(event.currency, (nextMonthExpected.get(event.currency) ?? 0) + Number(event.amount));
    }
  }
  const expected = [...nextMonthExpected.entries()].map(([currency, amount]) => [currency, String(amount)] as const);
  const unsupportedCurrencies = expected.filter(([currency]) => !rates.data?.rates[currency]).map(([currency]) => currency);
  const expectedCny = rates.data && unsupportedCurrencies.length === 0 ? expected.reduce((total, [currency, amount]) => total + Number(amount) * Number(rates.data.rates[currency]), 0) : null;
  const eventsIn30Days = (events.data ?? []).filter((event) => new Date(`${event.event_date}T00:00:00`).getTime() <= now.getTime() + 30 * 86_400_000);
  const names = new Map(subscriptions.data?.items.map((item) => [item.id, item.name]));
  return (
    <section>
      <header className="page-header"><div><p className="eyebrow">Dashboard</p><h1>今天，一切按计划。</h1><p className="muted">未来 30 天有 {eventsIn30Days.length} 个关键事件。</p></div><Link className="primary-button link-button" to="/subscriptions?create=1">＋ 新建订阅</Link></header>
      <div className="metric-grid">
        <article className="metric-card"><span>活跃订阅</span><strong>{subscriptions.data?.items.filter((item) => item.status === "active").length ?? 0}</strong><small>共 {subscriptions.data?.total ?? 0} 项</small></article>
        <article className="metric-card"><span>下月预计续费</span><div className="money-stack">{expected.length ? expected.map(([currency, amount]) => <strong key={currency}><Money amount={amount} currency={currency} /></strong>) : <strong>—</strong>}</div><small>{new Intl.DateTimeFormat("zh-CN", { year: "numeric", month: "long" }).format(nextMonthStart)}账单事件</small></article>
        <article className="metric-card"><span>下月人民币估算</span><div className="money-stack"><strong>{expectedCny === null ? "—" : <Money amount={String(expectedCny)} currency="CNY" />}</strong></div><small>{rates.data ? unsupportedCurrencies.length ? `${unsupportedCurrencies.join("、")} 无参考汇率，未合计` : `ECB ${rates.data.date} 参考汇率` : rates.isPending ? "正在获取最新参考汇率…" : "汇率暂不可用，未生成估算"}</small></article>
        <article className="metric-card"><span>即将发生</span><strong>{eventsIn30Days.length}</strong><small>未来 30 天关键事件</small></article>
      </div>
      <div className="dashboard-grid">
        <section className="panel"><div className="panel-heading"><div><p className="eyebrow">Timeline</p><h2>即将发生</h2></div><Link to="/events">查看全部</Link></div>{eventsIn30Days.length ? <div className="event-list">{eventsIn30Days.slice(0, 6).map((event) => <article key={event.id}><time>{new Intl.DateTimeFormat("zh-CN", { month: "short", day: "numeric" }).format(new Date(`${event.event_date}T00:00:00`))}</time><div><strong>{names.get(event.subscription_id) ?? "订阅"}</strong><span>{eventLabels[event.event_type] ?? event.event_type}</span></div>{event.amount && event.currency && <Money amount={event.amount} currency={event.currency} />}</article>)}</div> : <EmptyState title="未来很安静" message="未来 30 天没有账单或服务期限事件。" />}</section>
        <section className="panel"><div className="panel-heading"><div><p className="eyebrow">Portfolio</p><h2>最近订阅</h2></div><Link to="/subscriptions">管理</Link></div>{subscriptions.data?.items.length ? <div className="mini-subscriptions">{subscriptions.data.items.slice(0, 5).map((item) => <Link key={item.id} to={`/subscriptions/${item.id}`}><span className="service-mark">{item.name.slice(0, 1).toUpperCase()}</span><span><strong>{item.name}</strong><small>{item.billing_plan ? item.billing_plan.auto_renew ? `${item.billing_plan.currency} · ${item.billing_plan.next_billing_date ?? "无续费日"}` : `${item.billing_plan.currency} · 不自动续费` : "无计费计划"}</small></span><span className={`status-pill ${item.status}`}>{item.status}</span></Link>)}</div> : <EmptyState title="还没有订阅" message="创建第一项订阅后，它会出现在这里。" />}</section>
      </div>
    </section>
  );
}
