import { Navigate, Route, Routes } from "react-router-dom";

import { AppShell } from "./app/AppShell";
import { useSession } from "./app/session";
import { LoginPage } from "./pages/LoginPage";
import { DashboardPage } from "./pages/DashboardPage";
import { SubscriptionsPage } from "./pages/SubscriptionsPage";
import { SubscriptionDetailPage } from "./pages/SubscriptionDetailPage";
import { AnalyticsPage } from "./pages/AnalyticsPage";
import { EventsPage } from "./pages/EventsPage";
import { SettingsPage } from "./pages/SettingsPage";

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
        <Route path="settings" element={<SettingsPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
