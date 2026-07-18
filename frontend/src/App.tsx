import { Navigate, Route, Routes } from "react-router-dom";

import { AppShell } from "./app/AppShell";
import { useSession } from "./app/session";
import { LoginPage } from "./pages/LoginPage";
import { PlaceholderPage } from "./pages/PlaceholderPage";

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
        <Route index element={<PlaceholderPage title="总览" description="支出、续费和服务期限一目了然。" />} />
        <Route path="subscriptions" element={<PlaceholderPage title="订阅" description="集中管理所有数字服务。" />} />
        <Route path="events" element={<PlaceholderPage title="即将发生" description="查看未来账单和关键日期。" />} />
        <Route path="analytics" element={<PlaceholderPage title="统计" description="按币种理解预计与实际支出。" />} />
        <Route path="settings" element={<PlaceholderPage title="设置" description="管理会话、通知和 API Token。" />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
