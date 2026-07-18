import { Navigate, Route, Routes } from "react-router-dom";

import { AppShell } from "./app/AppShell";
import { useSession } from "./app/session";
import { LoginPage } from "./pages/LoginPage";
import { DashboardPage } from "./pages/DashboardPage";
import { PlaceholderPage } from "./pages/PlaceholderPage";
import { SubscriptionsPage } from "./pages/SubscriptionsPage";
import { SubscriptionDetailPage } from "./pages/SubscriptionDetailPage";
import { AnalyticsPage } from "./pages/AnalyticsPage";
import { EventsPage } from "./pages/EventsPage";

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
        <Route path="events" element={<EventsPage />} />
        <Route path="analytics" element={<AnalyticsPage />} />
        <Route path="settings" element={<PlaceholderPage title="设置" description="管理会话、通知和 API Token。" />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
