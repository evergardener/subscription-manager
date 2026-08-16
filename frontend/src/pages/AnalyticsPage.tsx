import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { analyticsSummary, listCategories, listSubscriptions } from "../api/business";
import { EmptyState, ErrorState, LoadingState } from "../components/AsyncState";
import { Money } from "../components/Money";

export function AnalyticsPage() {
  const [vendor, setVendor] = useState("");
  const [categoryId, setCategoryId] = useState("");
  const [scope, setScope] = useState<"current" | "all">("current");
  const analytics = useQuery({ queryKey: ["analytics", vendor, categoryId, scope], queryFn: ({ signal }) => analyticsSummary({ vendor: vendor || undefined, categoryId: categoryId || undefined, scope }, signal) });
  const subscriptions = useQuery({ queryKey: ["subscriptions", "", true], queryFn: ({ signal }) => listSubscriptions("", signal, true) });
  const categories = useQuery({ queryKey: ["categories"], queryFn: ({ signal }) => listCategories(signal) });
  if (analytics.isPending) return <LoadingState label="正在计算统计…" />;
  if (analytics.error) return <ErrorState error={analytics.error} />;
  const vendors = [...new Set((subscriptions.data?.items ?? []).map((item) => item.vendor).filter((name): name is string => Boolean(name)))].sort();
  const currencies = [...new Set([...Object.keys(analytics.data.expected_annual), ...Object.keys(analytics.data.actual), ...Object.keys(analytics.data.total_actual)])];
  return <section>
    <header className="page-header"><div><p className="eyebrow">Analytics</p><h1>支出统计</h1><p className="muted">预计年支出按当前计费计划折算为全年金额；实际支出分近 12 个月与累计总支出两个口径。</p></div></header>
    <div className="toolbar">
      <div className="filter-group">
        <label className="filter-field"><span>范围</span><select aria-label="按订阅范围筛选" value={scope} onChange={(event) => setScope(event.target.value as "current" | "all")}><option value="current">当前订阅中</option><option value="all">全部订阅（含已结束）</option></select></label>
        <label className="filter-field"><span>供应商</span><select aria-label="按供应商筛选" value={vendor} onChange={(event) => setVendor(event.target.value)}><option value="">全部供应商</option>{vendors.map((name) => <option key={name} value={name}>{name}</option>)}</select></label>
        <label className="filter-field"><span>分类</span><select aria-label="按分类筛选" value={categoryId} onChange={(event) => setCategoryId(event.target.value)}><option value="">全部分类</option>{(categories.data ?? []).map((category) => <option key={category.id} value={category.id}>{category.name}</option>)}</select></label>
      </div>
    </div>
    {currencies.length ? <div className="currency-grid">{currencies.map((currency) => { const rows: [string, string][] = [["预计年支出", analytics.data.expected_annual[currency] ?? "0"], ["实际已支出（近 12 个月）", analytics.data.actual[currency] ?? "0"], ["累计总支出（全部时间）", analytics.data.total_actual[currency] ?? "0"]]; const maximum = Math.max(...rows.map(([, amount]) => Number(amount)), 1); return <article className="panel" key={currency}><div className="panel-heading"><div><p className="eyebrow">{currency}</p><h2>{new Intl.DisplayNames(["zh-CN"], { type: "currency" }).of(currency)}</h2></div></div><div className="comparison">{rows.map(([label, amount], index) => <div key={label}><span>{label}</span><strong><Money amount={amount} currency={currency} /></strong><i className={index === 0 ? "" : "actual"} style={{ width: `${Number(amount) / maximum * 100}%` }} /></div>)}</div></article>; })}</div> : <EmptyState title="还没有统计数据" message="创建订阅并记录付款后，这里会展示预计年支出与实际支出。" />}
  </section>;
}
