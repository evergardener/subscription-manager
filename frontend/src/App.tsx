import { useQuery } from "@tanstack/react-query";

import { fetchLiveHealth } from "./api/health";

export function App() {
  const health = useQuery({
    queryKey: ["health", "live"],
    queryFn: ({ signal }) => fetchLiveHealth(signal),
    retry: false,
  });

  const state = health.isPending
    ? "正在连接 API"
    : health.isSuccess
      ? "API 已就绪"
      : "API 暂不可用";

  return (
    <main className="shell">
      <section className="hero" aria-labelledby="app-title">
        <p className="eyebrow">P0 · Architecture Validation</p>
        <h1 id="app-title">Hermes Subscription Manager</h1>
        <p className="summary">订阅与数字服务的自托管生命周期管理底座。</p>
        <div className="status" role="status" data-state={health.isSuccess ? "ok" : "pending"}>
          <span aria-hidden="true" className="status-dot" />
          {state}
        </div>
      </section>
    </main>
  );
}
