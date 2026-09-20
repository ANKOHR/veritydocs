"use client";

/* The evidence canvas needs an unoptimized API-served page image. */
/* eslint-disable @next/next/no-img-element */

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { API_URL, apiFetch, apiUpload } from "../lib/api";
import { Shell } from "./shell";

type Evidence = { document_id: string; page: number; text: string; bbox: number[] | null; section: string | null; artifact_key: string | null };
type Field = { id: string; field_name: string; value: unknown; confidence: number; extraction_confidence: number; ocr_confidence: number; validation_status: string; status: string; method: string; warnings: string[]; evidence: Evidence[] };
type Document = { id: string; filename: string; mime_type: string; size_bytes: number; page_count: number; document_type: string; classification_confidence: number; status: string; sha256: string; fields: Field[] };
type CaseData = { id: string; name: string; property_address: string | null; status: string; documents: Document[]; validations: { id: string; rule_id: string; status: string; message: string; expected: unknown; actual: unknown }[]; reconciliations: { id: string; metric: string; status: string; left_document_id: string | null; right_document_id: string | null; left_value: unknown; right_value: unknown; difference: number | null; message: string }[]; reviews: { id: string; document_id: string; field_id: string | null; status: string; reason: string; model_value: unknown; human_value: unknown; reviewer: string | null }[]; verified_field_count: number; reviewed_field_count: number; exception_count: number; overall_confidence: number };

export function CaseWorkspace({ caseId }: { caseId: string }) {
  const [data, setData] = useState<CaseData | null>(null);
  const [selected, setSelected] = useState<{ field: Field; document: Document } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [uploadBusy, setUploadBusy] = useState(false);
  const [uploadMessage, setUploadMessage] = useState<string | null>(null);
  async function load() { try { setData(await apiFetch<CaseData>(`/api/cases/${caseId}`)); } catch (err) { setError(err instanceof Error ? err.message : "Could not load case"); } }
  useEffect(() => {
    let active = true;
    apiFetch<CaseData>(`/api/cases/${caseId}`)
      .then((result) => { if (active) setData(result); })
      .catch((err: unknown) => { if (active) setError(err instanceof Error ? err.message : "Could not load case"); });
    return () => { active = false; };
  }, [caseId]);
  async function seed() { setBusy(true); try { await apiFetch(`/api/cases/${caseId}/demo-seed`, { method: "POST" }); await load(); } catch (err) { setError(err instanceof Error ? err.message : "Could not seed case"); } finally { setBusy(false); } }
  async function upload(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    setUploadBusy(true); setUploadMessage(`Uploading ${file.name}…`); setError(null);
    try {
      const queued = await apiUpload<{ document_id: string }>(
        `/api/cases/${caseId}/documents?run_pipeline=false`, file,
      );
      setUploadMessage("Queued for OCR and validation…");
      for (let attempt = 0; attempt < 30; attempt += 1) {
        await new Promise((resolve) => setTimeout(resolve, 1200));
        const latest = await apiFetch<CaseData>(`/api/cases/${caseId}`);
        setData(latest);
        const document = latest.documents.find((item) => item.id === queued.document_id);
        if (document?.status === "complete") { setUploadMessage("OCR and evidence processing complete."); break; }
        if (document?.status === "failed") throw new Error("The worker marked this document as failed.");
      }
    } catch (err) { setError(err instanceof Error ? err.message : "Could not process upload"); setUploadMessage(null); }
    finally { setUploadBusy(false); }
  }

  const fields = useMemo(() => data?.documents.flatMap((document) => document.fields.map((field) => ({ field, document }))) || [], [data]);
  if (!data) return <Shell active="Cases"><div className="loading-state">{error || "Loading case…"}<button className="secondary-button" onClick={seed} disabled={busy}>{busy ? "Processing…" : "Seed demo case"}</button></div></Shell>;
  const openReviews = data.reviews.filter((item) => item.status === "open");
  return <Shell active="Cases">
    <header className="topbar case-topbar"><div><div className="breadcrumb"><Link href="/">Cases</Link><span>/</span>{data.name}</div><h1>{data.name}</h1><p className="lede">{data.property_address || "Property address pending"} <span className="separator">•</span> {data.documents.length} source documents</p>{uploadMessage && <p className="upload-status">{uploadMessage}</p>}</div><div className="header-actions"><span className={`case-status ${data.status}`}>{data.status === "review" ? "Review required" : data.status}</span><label className="secondary-button upload-button">{uploadBusy ? "OCR processing…" : "Upload scan"}<input type="file" accept=".pdf,.png,.jpg,.jpeg,.webp,.xlsx,.xlsm,.csv" onChange={upload} disabled={uploadBusy} /></label><button className="secondary-button" onClick={seed} disabled={busy}>{busy ? "Reprocessing…" : "↻  Reprocess demo"}</button></div></header>
    <section className="case-stat-strip"><Stat label="Fields extracted" value={String(fields.length)} sub={`${data.verified_field_count} high-confidence`} /><Stat label="Overall confidence" value={`${Math.round(data.overall_confidence * 100)}%`} sub="Composite score" /><Stat label="Reconciliations" value={String(data.reconciliations.length)} sub={`${data.reconciliations.filter((x) => x.status === "RECONCILED").length} passed`} /><Stat label="Exceptions" value={String(data.exception_count)} sub={`${openReviews.length} in review queue`} danger={data.exception_count > 0} /></section>
    <section className="workspace-grid">
      <div className="workspace-main">
        <div className="panel-heading"><div><div className="eyebrow">CASE SUMMARY</div><h2>Underwriting facts</h2></div><span className="muted">Click a value to inspect evidence</span></div>
        <div className="facts-grid">
          {fields.filter(({ field }) => field.field_name !== "units").map(({ field, document }) => <button className={`fact-card ${selected?.field.id === field.id ? "selected" : ""}`} key={field.id} onClick={() => setSelected({ field, document })}><span className="fact-label">{pretty(field.field_name)}</span><strong>{formatValue(field.value)}</strong><span className="fact-meta"><span className={field.confidence >= .85 ? "confidence good" : "confidence warn"}>{Math.round(field.confidence * 100)}% confidence</span><span>{document.filename}</span></span></button>)}
        </div>
        <div className="panel-heading subsection"><div><div className="eyebrow">RECONCILIATION GRAPH</div><h2>What agrees, what does not</h2></div></div>
        <div className="reconciliation-list">{data.reconciliations.map((item) => <div className={`recon-row ${item.status.toLowerCase()}`} key={item.id}><span className="recon-icon">{item.status === "RECONCILED" ? "✓" : item.status === "CONFLICT" ? "!" : "?"}</span><div><strong>{pretty(item.metric)}</strong><p>{item.message}</p></div><span className="recon-status">{item.status.replaceAll("_", " ")}</span></div>)}{!data.reconciliations.length && <p className="muted">Add at least two compatible documents to reconcile case facts.</p>}</div>
        <div className="panel-heading subsection"><div><div className="eyebrow">SOURCE DOCUMENTS</div><h2>Processing trace</h2></div></div>
        <div className="document-list">{data.documents.map((document) => <div className="document-row" key={document.id}><div className="file-icon">{document.mime_type.includes("spreadsheet") ? "XLS" : "PDF"}</div><div className="document-info"><strong>{document.filename}</strong><span>{pretty(document.document_type)} <span className="separator">•</span> {document.page_count} page{document.page_count === 1 ? "" : "s"}</span></div><span className={`processing-status ${document.status}`}>{document.status}</span></div>)}</div>
      </div>
      <aside className="evidence-panel"><div className="evidence-header"><div><div className="eyebrow">EVIDENCE VIEWER</div><h2>{selected ? pretty(selected.field.field_name) : "Select a field"}</h2></div>{selected && <span className="confidence-badge">{Math.round(selected.field.confidence * 100)}%</span>}</div>{selected ? <EvidenceViewer selected={selected} /> : <div className="evidence-empty"><div className="crosshair">⌖</div><h3>Source-level provenance</h3><p>Choose a financial fact to open its source excerpt, page reference and validation trail.</p><div className="empty-rule" /><span>Evidence is stored with the extracted value</span></div>}</aside>
    </section>
    <section className="review-panel"><div className="panel-heading"><div><div className="eyebrow">HUMAN REVIEW</div><h2>Exceptions that should not be guessed</h2></div><span className="review-count">{openReviews.length} open</span></div>{openReviews.length ? <div className="review-list">{openReviews.map((review) => <div className="review-row" key={review.id}><div className="review-warning">!</div><div><strong>{review.reason}</strong><p>Model value: {formatValue(review.model_value)} <span className="separator">•</span> {review.document_id}</p></div><button className="ghost-button" onClick={() => void resolveReview(review.id, load)}>Mark unable to verify</button></div>)}</div> : <div className="clear-review"><span>✓</span> No unresolved review items</div>}</section>
  </Shell>;
}

function EvidenceViewer({ selected }: { selected: { field: Field; document: Document } }) {
  const evidence = selected.field.evidence[0];
  const [imageFailed, setImageFailed] = useState(false);
  const [imageSize, setImageSize] = useState({ width: 0, height: 0 });
  if (!evidence) return <div className="evidence-empty"><div className="crosshair">?</div><h3>Unable to verify source span</h3><p>The field was typed successfully, but no exact source region matched. This is deliberately visible instead of being silently asserted.</p><span className="review-chip">Review recommended</span></div>;
  const pageUrl = `${API_URL}/api/documents/${evidence.document_id}/pages/${evidence.page}`;
  const bbox = evidence.bbox && evidence.bbox.length === 4 && imageSize.width > 0 ? evidence.bbox : null;
  return <div className="evidence-content"><div className="source-toolbar"><span>{selected.document.filename}</span><span>PAGE {evidence.page}</span></div><div className="source-canvas">{imageFailed ? <div className="source-fallback"><span className="scan-line" /><strong>{evidence.text}</strong><span className="highlight-caption">Matched evidence</span></div> : <div className="source-image-wrap"><img src={pageUrl} alt={`Page ${evidence.page} from ${selected.document.filename}`} onLoad={(event) => setImageSize({ width: event.currentTarget.naturalWidth, height: event.currentTarget.naturalHeight })} onError={() => setImageFailed(true)} />{bbox && <span className="evidence-highlight" style={{ left: `${bbox[0] / imageSize.width * 100}%`, top: `${bbox[1] / imageSize.height * 100}%`, width: `${(bbox[2] - bbox[0]) / imageSize.width * 100}%`, height: `${(bbox[3] - bbox[1]) / imageSize.height * 100}%` }} />}</div>}</div><div className="evidence-detail"><div><span className="detail-label">SOURCE</span><strong>{selected.document.filename}</strong></div><div><span className="detail-label">PAGE / SECTION</span><strong>{evidence.page} {evidence.section ? `· ${evidence.section}` : ""}</strong></div><div><span className="detail-label">METHOD</span><strong>{selected.field.method}</strong></div></div><div className="validation-trail"><div className="trail-title">Validation trail</div><div><span>✓</span> Typed schema accepted</div><div><span>✓</span> Source span linked</div><div><span>{selected.field.validation_status === "FAIL" ? "!" : "✓"}</span> {selected.field.validation_status === "NOT_CHECKED" ? "No arithmetic rule applies" : selected.field.validation_status}</div></div></div>;
}

function Stat({ label, value, sub, danger = false }: { label: string; value: string; sub: string; danger?: boolean }) { return <div className="case-stat"><span>{label}</span><strong className={danger ? "danger-text" : ""}>{value}</strong><small>{sub}</small></div>; }
function pretty(value: string) { return value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase()); }
function formatValue(value: unknown): string { if (value === null || value === undefined || value === "") return "Unable to verify"; if (Array.isArray(value)) return `${value.length} records`; if (typeof value === "object") return "Structured record"; if (typeof value === "string" && /^\d{4}-\d{2}-\d{2}$/.test(value)) return new Intl.DateTimeFormat("en-GB", { dateStyle: "medium" }).format(new Date(value)); return String(value); }
async function resolveReview(reviewId: string, load: () => Promise<void>) { await apiFetch(`/api/review/${reviewId}/resolve`, { method: "POST", body: JSON.stringify({ decision: "unable_to_verify", reviewer: "operator", reason: "Source does not support a verified value." }) }); await load(); }
