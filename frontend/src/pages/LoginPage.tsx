import { useQuery } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Navigate } from "react-router-dom";

import { bootstrap, bootstrapRequired } from "../api/auth";
import { ApiError } from "../api/client";
import { useSession } from "../app/session";

export function LoginPage() {
  const { session, signIn } = useSession();
  const bootstrapStatus = useQuery({ queryKey: ["bootstrap-required"], queryFn: ({ signal }) => bootstrapRequired(signal), retry: false });
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  if (session) return <Navigate to="/" replace />;
  const setup = bootstrapStatus.data?.required ?? false;

  async function submit(event: FormEvent) {
    event.preventDefault();
    setSubmitting(true);
    setMessage(null);
    try {
      if (setup) {
        if (password !== confirm) {
          setMessage("两次输入的密码不一致");
          return;
        }
        await bootstrap(username, password);
      }
      await signIn(username, password);
    } catch (reason) {
      setMessage(
        reason instanceof ApiError && reason.status === 401
          ? "用户名或密码不正确"
          : reason instanceof ApiError && reason.status === 409
            ? "管理员已存在，请直接登录"
            : setup
              ? "创建失败，请稍后重试"
              : "登录失败，请稍后重试",
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="login-page">
      <section className="login-panel" aria-labelledby="login-title">
        <div className="brand brand-large"><span className="brand-mark">S</span><span>Subscription Manager</span></div>
        <p className="eyebrow">Subscription Manager</p>
        <h1 id="login-title">{setup ? "首次设置" : "欢迎回来"}</h1>
        <p className="muted">{setup ? "创建第一个管理员账号以开始使用。" : "登录以管理订阅、付款与续费提醒。"}</p>
        <form onSubmit={(event) => void submit(event)}>
          <label>用户名<input autoComplete="username" required value={username} onChange={(e) => setUsername(e.target.value)} /></label>
          <label>密码<input autoComplete={setup ? "new-password" : "current-password"} minLength={12} required type="password" value={password} onChange={(e) => setPassword(e.target.value)} /></label>
          {setup && <label>确认密码<input autoComplete="new-password" minLength={12} required type="password" value={confirm} onChange={(e) => setConfirm(e.target.value)} /></label>}
          {message && <div className="alert error" role="alert">{message}</div>}
          <button className="primary-button" disabled={submitting || bootstrapStatus.isPending} type="submit">{submitting ? (setup ? "正在创建…" : "正在登录…") : (setup ? "创建并登录" : "登录")}</button>
        </form>
        {!setup && <p className="login-help">忘记密码请参考 README 的本机恢复流程。</p>}
      </section>
      <section className="login-art" aria-hidden="true"><div className="orbit orbit-one" /><div className="orbit orbit-two" /><div className="art-copy"><strong>让每一项订阅<br />都按计划运行。</strong><span>清晰掌握支出、续费和服务期限。</span></div></section>
    </main>
  );
}
