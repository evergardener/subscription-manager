export function PlaceholderPage({ title, description }: { title: string; description: string }) {
  return (
    <section>
      <header className="page-header"><div><p className="eyebrow">Hermes Workspace</p><h1>{title}</h1><p className="muted">{description}</p></div></header>
      <div className="empty-card"><span className="empty-icon">◇</span><h2>正在构建这部分体验</h2><p>应用安全壳已就绪，业务数据将在下一个经过验证的提交中接入。</p></div>
    </section>
  );
}
