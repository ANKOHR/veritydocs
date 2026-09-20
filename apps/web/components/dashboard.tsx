"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { API_URL, apiFetch } from "../lib/api";
import { Shell } from "./shell";

type CaseItem = { id: string; name: string; property_address: string | null; status: string; document_count: number; exception_count: number; overall_confidence: number };

export function Dashboard() {
  const router = useRouter();
  const [cases, setCases] = useState<CaseItem[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    try { setCases(await apiFetch<CaseItem[]>("/api/cases")); } catch (err) { setError(err instanceof Error ? err.message : "API unavailable"); }
  }
  useEffect(() => {
    let active = true;
    apiFetch<CaseItem[]>("/api/cases")
      .then((result) => { if (active) setCases(result); })
      .catch((err: unknown) => { if (active) setError(err instanceof Error ? err.message : "API unavailable"); });
    return () => { active = false; };
  }, []);

  async function createDemo() {
    setBusy(true); setError(null);
    try {
      const created = await apiFetch<{ id: string }>("/api/cases", { method: "POST", body: JSON.stringify({ name: "Acme Property Acquisition", property_address: "32 New Street, London" }) });
      await apiFetch(`/api/cases/${created.id}/demo-seed`, { method: "POST" });
      router.push(`/cases/${created.id}`);
    } catch (err) { setError(err instanceof Error ? err.message : "Could not create demo case"); setBusy(false); }
  }

  const totalDocs = cases.reduce((sum, item) => sum + item.document_count, 0);
  const totalExceptions = cases.reduce((sum, item) => sum + item.exception_count, 0);
  return (
    <Shell active="Cases">
      <header className="topbar"><div><div className="eyebrow">OPERATIONS / CASES</div><h1>Document intelligence, with receipts.</h1><p className="lede">Extract trusted records from messy files, reconcile them across sources, and keep uncertainty visible.</p></div><button className="primary-button" onClick={createDemo} disabled={busy}>{busy ? "Processing…" : "+  New demo case"}</button></header>
      {error && <div className="error-banner">{error}<span>Check that the FastAPI service is running at {API_URL}.</span></div>}
      <section className="metric-grid">
        <Metric label="Active cases" value={String(cases.length).padStart(2, "0")} detail="Evidence workspaces" tone="blue" />
        <Metric label="Documents processed" value={String(totalDocs).padStart(2, "0")} detail="PDF, XLSX and image inputs" tone="violet" />
        <Metric label="Open exceptions" value={String(totalExceptions).padStart(2, "0")} detail="Human attention required" tone="amber" />
        <Metric label="Evidence coverage" value={cases.length ? `${Math.round(cases.reduce((sum, item) => sum + item.overall_confidence, 0) / cases.length * 100)}%` : "—"} detail="Composite confidence" tone="green" />
      </section>
      <section className="section-heading"><div><div className="eyebrow">WORKSPACES</div><h2>Recent cases</h2></div><span className="muted">{cases.length} total</span></section>
      <section className="case-grid">
        {cases.map((item) => <Link className="case-card" href={`/cases/${item.id}`} key={item.id}><div className="case-card-top"><span className={`case-status ${item.status}`}>{item.status === "review" ? "Needs review" : item.status}</span><span className="arrow">↗</span></div><h3>{item.name}</h3><p>{item.property_address || "No address provided"}</p><div className="case-card-footer"><span>{item.document_count} documents</span><span>{Math.round(item.overall_confidence * 100)}% confidence</span></div></Link>)}
        {!cases.length && <div className="empty-state"><div className="empty-icon">✦</div><h3>Start with the flagship property case</h3><p>Seed four deliberately messy-but-structured documents and inspect provenance, reconciliation and review routing in one workspace.</p><button className="secondary-button" onClick={createDemo} disabled={busy}>{busy ? "Building case…" : "Create Acme demo"}</button></div>}
      </section>
      <section className="principles"><div><div className="eyebrow">PRODUCT PRINCIPLE</div><h2>Every important value should answer: “where did this come from?”</h2></div><div className="principle-copy"><span className="quote-mark">“</span><p>VerityDocs does not hide conflicts behind a polished summary. It preserves the source, checks the arithmetic, and routes uncertainty to a person.</p></div></section>
    </Shell>
  );
}

function Metric({ label, value, detail, tone }: { label: string; value: string; detail: string; tone: string }) { return <div className={`metric-card ${tone}`}><span className="metric-label">{label}</span><strong>{value}</strong><span className="metric-detail">{detail}</span></div>; }
