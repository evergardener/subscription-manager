import { useQuery } from "@tanstack/react-query";

import { listSubscriptions, upcomingEvents, type EventItem } from "../api/business";
import { EmptyState, ErrorState, LoadingState } from "../components/AsyncState";
import { Money } from "../components/Money";

const labels: Record<string, { label: string; icon: string }> = { billing: { label: "账单续费", icon: "↻" }, expiry: { label: "服务到期", icon: "⌛" }, trial_end: { label: "试用结束", icon: "△" }, cancellation_deadline: { label: "取消截止", icon: "!" }, contract_end: { label: "合同结束", icon: "□" } };

export function EventsPage() {
  const events = useQuery({ queryKey: ["events", 30], queryFn: ({ signal }) => upcomingEvents(30, signal) });
  const subscriptions = useQuery({ queryKey: ["subscriptions", "events"], queryFn: ({ signal }) => listSubscriptions("", signal) });
  if (events.isPending || subscriptions.isPending) return <LoadingState label="正在加载未来事件…" />;
  const error = events.error ?? subscriptions.error;
  if (error) return <ErrorState error={error} />;
  const names = new Map(subscriptions.data?.items.map((item) => [item.id, item.name]));
  const groups = new Map<string, EventItem[]>();
  for (const event of events.data ?? []) {
    groups.set(event.event_date, [...(groups.get(event.event_date) ?? []), event]);
  }
  return <section><header className="page-header"><div><p className="eyebrow">Upcoming events</p><h1>未来 30 天</h1><p className="muted">账单与关键服务日期按时间排列。</p></div><span className="count-badge">{events.data?.length ?? 0} 个事件</span></header>{events.data?.length ? <div className="timeline">{[...groups].map(([day, items]) => <section key={day}><header><time>{new Intl.DateTimeFormat("zh-CN", { month: "long", day: "numeric", weekday: "short" }).format(new Date(`${day}T00:00:00`))}</time></header><div>{items.map((event) => { const meta = labels[event.event_type] ?? { label: event.event_type, icon: "•" }; return <article key={event.id}><span className="event-icon">{meta.icon}</span><div><strong>{names.get(event.subscription_id) ?? "订阅"}</strong><small>{meta.label}</small></div>{event.amount && event.currency ? <Money amount={event.amount} currency={event.currency} /> : <span className="muted">关键日期</span>}</article>; })}</div></section>)}</div> : <EmptyState title="暂无未来事件" message="未来 30 天没有账单、到期或取消截止事件。" />}</section>;
}
