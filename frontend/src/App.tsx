import { Navigate, Route, Routes } from "react-router-dom";

import { AppShell } from "./app/AppShell";
import { useSession } from "./app/session";
import { LoginPage } from "./pages/LoginPage";
import { DashboardPage } from "./pages/DashboardPage";
import { PlaceholderPage } from "./pages/PlaceholderPage";
import { SubscriptionsPage } from "./pages/SubscriptionsPage";
import { SubscriptionDetailPage } from "./pages/SubscriptionDetailPage";

function ProtectedApp() {
  const { session, isLoading, error } = useSession();
  if (isLoading) return <main className="center-state"><div className="spinner" /><p>正在恢复会话…</p></main>;
  if (error) return <main className="center-state"><div className="alert error">{error}</div></main>;
  if (!session) return <Navigate to="/login" replace />;
  return <AppShell />;
}

export function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route element={<ProtectedApp />}>
        <Route index element={<DashboardPage />} />
        <Route path="subscriptions" element={<SubscriptionsPage />} />
        <Route path="subscriptions/:subscriptionId" element={<SubscriptionDetailPage />} />
        <Route path="events" element={<PlaceholderPage title="即将发生" description="查看未来账单和关键日期。" />} />
        <Route path="analytics" element={<PlaceholderPage title="统计" description="按币种理解预计与实际支出。" />} />
        <Route path="settings" element={<PlaceholderPage title="设置" description="管理会话、通知和 API Token。" />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
