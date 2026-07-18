import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState, type FormEvent } from "react";

import { createApiToken, listApiTokens, revokeApiToken } from "../api/auth";
import { useSession } from "../app/session";
import { EmptyState, ErrorState, LoadingState } from "../components/AsyncState";
import { clearBusinessCache } from "../offline/cache";
import { useOffline } from "../offline/OfflineProvider";

const availableScopes = ["subscriptions:read", "subscriptions:write", "payments:write", "analytics:read", "audit:read", "reminders:scan", "reminders:read"];

export function SettingsPage() {
  const { session } = useSession();
  const { offline } = useOffline();
  const queryClient = useQueryClient();
  const tokens = useQuery({ queryKey: ["api-tokens"], queryFn: ({ signal }) => listApiTokens(signal) });
  const [dialog, setDialog] = useState(false);
  const [revealedToken, setRevealedToken] = useState<string | null>(null);
  const [theme, setTheme] = useState(() => localStorage.getItem("hermes-theme") ?? "system");
  const [timezone, setTimezone] = useState(() => localStorage.getItem("hermes-timezone") ?? Intl.DateTimeFormat().resolvedOptions().timeZone);
  const [defaultReminder, setDefaultReminder] = useState(() => localStorage.getItem("hermes-default-reminder") ?? "5,1");
  const [persistentCache, setPersistentCache] = useState(() => localStorage.getItem("hermes-persistent-cache") !== "false");
  useEffect(() => { document.documentElement.dataset.theme = theme === "system" ? "" : theme; localStorage.setItem("hermes-theme", theme); }, [theme]);
  const create = useMutation({ mutationFn: createApiToken, onSuccess: async (result) => { setRevealedToken(result.token); setDialog(false); await queryClient.invalidateQueries({ queryKey: ["api-tokens"] }); } });
  const revoke = useMutation({ mutationFn: revokeApiToken, onSuccess: () => queryClient.invalidateQueries({ queryKey: ["api-tokens"] }) });
  async function savePreferences(event: FormEvent) { event.preventDefault(); localStorage.setItem("hermes-timezone", timezone); localStorage.setItem("hermes-default-reminder", defaultReminder); localStorage.setItem("hermes-persistent-cache", String(persistentCache)); if (!persistentCache) await clearBusinessCache(); }
  if (tokens.isPending) return <LoadingState label="正在加载设置…" />;
  return <section><header className="page-header"><div><p className="eyebrow">Settings</p><h1>设置</h1><p className="muted">会话、显示偏好与自动化访问。</p></div></header>
    <div className="settings-grid"><div className="settings-main">
      <section className="panel"><div className="panel-heading"><div><p className="eyebrow">Preferences</p><h2>显示与区域</h2></div></div><form onSubmit={(event) => void savePreferences(event)}><div className="form-grid"><label>主题<select value={theme} onChange={(event) => setTheme(event.target.value)}><option value="system">跟随系统</option><option value="light">浅色</option><option value="dark">深色</option></select></label><label>时区<input value={timezone} onChange={(event) => setTimezone(event.target.value)} /></label><label>默认提醒（提前天数）<input value={defaultReminder} pattern="[0-9]+(,[0-9]+)?" onChange={(event) => setDefaultReminder(event.target.value)} /></label><label className="cache-toggle"><input type="checkbox" checked={persistentCache} onChange={(event) => setPersistentCache(event.target.checked)} />允许在此设备保存最近只读数据</label></div><div className="modal-actions"><button className="primary-button" type="submit">保存偏好</button></div></form></section>
      <section className="panel"><div className="panel-heading"><div><p className="eyebrow">API access</p><h2>API Token</h2></div><button className="text-button" disabled={offline} onClick={() => setDialog(true)}>＋ 创建</button></div><p className="muted">为 Hermes 或自动化客户端创建最小权限、可撤销的独立 Token。</p>{tokens.error ? <ErrorState error={tokens.error} /> : tokens.data?.length ? <div className="token-list">{tokens.data.map((token) => <article key={token.id} className={token.revoked_at ? "revoked" : ""}><div><strong>{token.name}</strong><span>{token.actor_id} · {token.scopes.join(" · ")}</span></div><span>{token.revoked_at ? "已撤销" : token.expires_at ? `到期 ${token.expires_at.slice(0, 10)}` : "长期有效"}</span>{!token.revoked_at && <button className="danger-button" disabled={offline || revoke.isPending} onClick={() => { if (window.confirm(`确认撤销 Token“${token.name}”？此操作不可恢复。`)) revoke.mutate(token.id); }}>撤销</button>}</article>)}</div> : <EmptyState title="没有 API Token" message="Web UI 不需要 Token；仅为 Hermes 或自动化按需创建。" />}</section>
    </div><aside className="settings-side"><section className="panel"><p className="eyebrow">Current session</p><h2>{session?.actor_id}</h2><div className="date-list"><span><small>主体类型</small>{session?.actor_type}</span><span><small>Cookie</small>HttpOnly · SameSite Strict</span><span><small>CSRF</small>会话恢复时轮换</span></div></section><section className="panel"><p className="eyebrow">Notifications</p><h2>ntfy</h2><p className="muted">通知地址和 Topic 仅由服务器环境变量管理，不会发送到浏览器。替换 <code>NTFY_TOPIC=replace-me</code> 后 Scheduler 才会实际发送。</p></section></aside></div>
    {dialog && <TokenDialog pending={create.isPending} error={create.error} onClose={() => setDialog(false)} onSubmit={(payload) => create.mutate(payload)} />}
    {revealedToken && <TokenReveal token={revealedToken} onClose={() => setRevealedToken(null)} />}
  </section>;
}

function TokenDialog({ pending, error, onClose, onSubmit }: { pending: boolean; error: unknown; onClose: () => void; onSubmit: (payload: { name: string; actor_id: string; scopes: string[] }) => void }) {
  function submit(event: FormEvent<HTMLFormElement>) { event.preventDefault(); const data = new FormData(event.currentTarget); const text = (name: string) => { const value = data.get(name); return typeof value === "string" ? value : ""; }; onSubmit({ name: text("name"), actor_id: text("actor_id"), scopes: data.getAll("scopes").filter((value): value is string => typeof value === "string") }); }
  return <div className="modal-backdrop"><section className="modal" role="dialog" aria-modal="true" aria-label="创建 API Token"><div className="panel-heading"><h2>创建 API Token</h2><button className="icon-button" onClick={onClose} aria-label="关闭">×</button></div><form onSubmit={submit}><div className="form-grid"><label>名称<input name="name" required maxLength={200} /></label><label>Actor ID<input name="actor_id" defaultValue="hermes" required maxLength={200} /></label></div><fieldset><legend>权限范围</legend><div className="scope-grid">{availableScopes.map((scope) => <label key={scope}><input type="checkbox" name="scopes" value={scope} defaultChecked={scope === "subscriptions:read"} />{scope}</label>)}</div></fieldset>{error ? <ErrorState error={error} /> : null}<div className="modal-actions"><button className="secondary-button" type="button" onClick={onClose}>取消</button><button className="primary-button" disabled={pending} type="submit">{pending ? "正在创建…" : "创建 Token"}</button></div></form></section></div>;
}

function TokenReveal({ token, onClose }: { token: string; onClose: () => void }) {
  const [copied, setCopied] = useState(false);
  async function copy() { await navigator.clipboard.writeText(token); setCopied(true); }
  return <div className="modal-backdrop"><section className="modal token-reveal" role="dialog" aria-modal="true" aria-label="保存 API Token"><p className="eyebrow">仅显示一次</p><h2>立即保存此 Token</h2><p className="muted">关闭后无法再次查看明文；遗失时请撤销并重新创建。</p><code>{token}</code><div className="modal-actions"><button className="secondary-button" onClick={() => void copy()}>{copied ? "已复制" : "复制"}</button><button className="primary-button" onClick={onClose}>我已安全保存</button></div></section></div>;
}
