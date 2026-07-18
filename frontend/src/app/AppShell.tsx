import { NavLink, Outlet } from "react-router-dom";

import { useSession } from "./session";
import { useOffline } from "../offline/OfflineProvider";

const navigation = [
  ["/", "总览", "⌂"],
  ["/subscriptions", "订阅", "▦"],
  ["/events", "事件", "◷"],
  ["/analytics", "统计", "◒"],
  ["/settings", "设置", "⚙"],
] as const;

export function AppShell() {
  const { session, signOut } = useSession();
  const { offline, stale } = useOffline();
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand"><span className="brand-mark">H</span><span>Hermes</span></div>
        <nav aria-label="主导航">
          {navigation.map(([to, label, icon]) => (
            <NavLink key={to} to={to} end={to === "/"}>
              <span aria-hidden="true">{icon}</span><span>{label}</span>
            </NavLink>
          ))}
        </nav>
        <div className="account">
          <span className="avatar">{session?.actor_id.slice(0, 1).toUpperCase()}</span>
          <span className="account-name">{session?.actor_id}</span>
          <button className="icon-button" onClick={() => void signOut()} aria-label="退出登录">↪</button>
        </div>
      </aside>
      <main className="page">{offline && <div className="offline-banner" role="status"><strong>离线只读</strong><span>{stale ? "正在显示最近缓存，数据可能已过期。" : "写操作已禁用；可继续查看已缓存数据。"}</span></div>}<Outlet /></main>
      <nav className="bottom-nav" aria-label="移动端主导航">
        {navigation.map(([to, label, icon]) => (
          <NavLink key={to} to={to} end={to === "/"}>
            <span aria-hidden="true">{icon}</span><small>{label}</small>
          </NavLink>
        ))}
      </nav>
    </div>
  );
}
