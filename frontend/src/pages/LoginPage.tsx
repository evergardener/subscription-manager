import { useState, type FormEvent } from "react";
import { Navigate } from "react-router-dom";

import { ApiError } from "../api/client";
import { useSession } from "../app/session";

export function LoginPage() {
  const { session, signIn } = useSession();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  if (session) return <Navigate to="/" replace />;

  async function submit(event: FormEvent) {
    event.preventDefault();
    setSubmitting(true);
    setMessage(null);
    try {
      await signIn(username, password);
    } catch (reason) {
      setMessage(reason instanceof ApiError && reason.status === 401 ? "用户名或密码不正确" : "登录失败，请稍后重试");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="login-page">
      <section className="login-panel" aria-labelledby="login-title">
        <div className="brand brand-large"><span className="brand-mark">S</span><span>Subscription Manager</span></div>
        <p className="eyebrow">Subscription Manager</p>
        <h1 id="login-title">欢迎回来</h1>
        <p className="muted">登录以管理订阅、付款与续费提醒。</p>
        <form onSubmit={(event) => void submit(event)}>
          <label>用户名<input autoComplete="username" required value={username} onChange={(e) => setUsername(e.target.value)} /></label>
          <label>密码<input autoComplete="current-password" minLength={12} required type="password" value={password} onChange={(e) => setPassword(e.target.value)} /></label>
          {message && <div className="alert error" role="alert">{message}</div>}
          <button className="primary-button" disabled={submitting} type="submit">{submitting ? "正在登录…" : "登录"}</button>
        </form>
        <p className="login-help">首次使用请按 README 通过本机 API 创建管理员。</p>
      </section>
      <section className="login-art" aria-hidden="true"><div className="orbit orbit-one" /><div className="orbit orbit-two" /><div className="art-copy"><strong>让每一项订阅<br />都按计划运行。</strong><span>清晰掌握支出、续费和服务期限。</span></div></section>
    </main>
  );
}
