import { useQuery } from "@tanstack/react-query";

import { analyticsSummary, type AnalyticsBreakdown } from "../api/business";
import { EmptyState, ErrorState, LoadingState } from "../components/AsyncState";
import { Money } from "../components/Money";

export function AnalyticsPage() {
  const analytics = useQuery({ queryKey: ["analytics"], queryFn: ({ signal }) => analyticsSummary(signal) });
  if (analytics.isPending) return <LoadingState label="正在计算统计…" />;
  if (analytics.error) return <ErrorState error={analytics.error} />;
  const currencies = [...new Set([...Object.keys(analytics.data.expected), ...Object.keys(analytics.data.actual)])];
  return <section><header className="page-header"><div><p className="eyebrow">Analytics</p><h1>支出统计</h1><p className="muted">预计与实际金额始终按币种分别展示。</p></div></header>{currencies.length ? <><div className="currency-grid">{currencies.map((currency) => { const expected = analytics.data.expected[currency] ?? "0"; const actual = analytics.data.actual[currency] ?? "0"; const maximum = Math.max(Number(expected), Number(actual), 1); return <article className="panel" key={currency}><div className="panel-heading"><div><p className="eyebrow">{currency}</p><h2>{new Intl.DisplayNames(["zh-CN"], { type: "currency" }).of(currency)}</h2></div></div><div className="comparison"><div><span>预计</span><strong><Money amount={expected} currency={currency} /></strong><i style={{ width: `${Number(expected) / maximum * 100}%` }} /></div><div><span>实际</span><strong><Money amount={actual} currency={currency} /></strong><i className="actual" style={{ width: `${Number(actual) / maximum * 100}%` }} /></div></div></article>; })}</div><div className="analytics-grid"><Breakdown title="按供应商" rows={analytics.data.by_vendor} /><Breakdown title="按分类" rows={analytics.data.by_category} /></div></> : <EmptyState title="还没有统计数据" message="创建订阅并记录付款后，这里会展示预计与实际支出。" />}</section>;
}

function Breakdown({ title, rows }: { title: string; rows: AnalyticsBreakdown[] }) {
  return <section className="panel"><div className="panel-heading"><div><p className="eyebrow">Breakdown</p><h2>{title}</h2></div></div>{rows.length ? <div className="breakdown-list">{rows.map((row) => <article key={`${row.currency}-${row.label}`}><strong>{row.label}</strong><span><Money amount={row.expected} currency={row.currency} /> <small>预计</small></span><span><Money amount={row.actual} currency={row.currency} /> <small>实际</small></span></article>)}</div> : <p className="muted">暂无数据。</p>}</section>;
}
