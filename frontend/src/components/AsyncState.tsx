import { ApiError } from "../api/client";

export function LoadingState({ label = "正在加载…" }: { label?: string }) {
  return <div className="inline-state"><div className="spinner" /><span>{label}</span></div>;
}

export function ErrorState({ error }: { error: unknown }) {
  const message = error instanceof ApiError ? error.message : "数据加载失败，请稍后重试";
  return <div className="alert error" role="alert">{message}</div>;
}

export function EmptyState({ title, message }: { title: string; message: string }) {
  return <div className="empty-card compact"><span className="empty-icon">◇</span><h2>{title}</h2><p>{message}</p></div>;
}
