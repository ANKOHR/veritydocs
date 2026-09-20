"use client";

import Link from "next/link";

export function Shell({ children, active = "Cases" }: { children: React.ReactNode; active?: string }) {
  const navigation = ["Overview", "Cases", "Documents", "Review", "Evaluations", "Analytics"];
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">V</div>
          <div>
            <div className="brand-name">VerityDocs</div>
            <div className="brand-subtitle">DOCUMENT INTELLIGENCE</div>
          </div>
        </div>
        <div className="workspace-switcher">
          <span className="avatar">H</span>
          <span><strong>Henry&apos;s workspace</strong><small>Demo tenant</small></span>
          <span className="chevron">⌄</span>
        </div>
        <nav className="nav-list">
          {navigation.map((item) => {
            const href = item === "Cases" || item === "Overview" ? "/" : `/#${item.toLowerCase()}`;
            return <Link className={active === item ? "nav-item active" : "nav-item"} href={href} key={item}><span className="nav-icon">{iconFor(item)}</span>{item}</Link>;
          })}
        </nav>
        <div className="sidebar-footer">
          <div className="pipeline-pill"><span className="status-dot" /> Pipeline healthy <span className="version">v0.1</span></div>
          <div className="user-row"><span className="avatar warm">H</span><span><strong>Henry</strong><small>Operator</small></span><span className="more">•••</span></div>
        </div>
      </aside>
      <main className="main-content">{children}</main>
    </div>
  );
}

function iconFor(item: string) {
  const icons: Record<string, string> = { Overview: "◫", Cases: "▣", Documents: "▤", Review: "✓", Evaluations: "⌁", Analytics: "◒" };
  return icons[item] || "·";
}
