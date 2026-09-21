from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, HTMLResponse

router = APIRouter(tags=["demo"])

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
FIXTURE_ROOT = REPOSITORY_ROOT / "fixtures"


@dataclass(frozen=True)
class DemoSample:
    sample_id: str
    label: str
    filename: str
    description: str

    @property
    def path(self) -> Path:
        return FIXTURE_ROOT / self.filename


DEMO_SAMPLES = (
    DemoSample(
        "clean",
        "Clean sample",
        "invoice_inv_0042_scan.pdf",
        "Net £8,000.00 plus VAT £1,600.00, with gross £9,600.00.",
    ),
    DemoSample(
        "totals-mismatch",
        "Totals mismatch sample",
        "invoice_inv_0042_inconsistent_scan.pdf",
        "The same net and VAT values state a gross total of £9,900.00.",
    ),
    DemoSample(
        "missing-field",
        "Missing field sample",
        "invoice_inv_0042_missing_tax_scan.pdf",
        "The invoice does not state VAT, so FIN-001 cannot be verified.",
    ),
)
DEMO_SAMPLE_BY_ID = {sample.sample_id: sample for sample in DEMO_SAMPLES}


@router.get("/demo", response_class=HTMLResponse)
def demo_page() -> HTMLResponse:
    return HTMLResponse(DEMO_PAGE)


@router.get("/demo/samples/{sample_id}")
def demo_sample(sample_id: str) -> FileResponse:
    sample = DEMO_SAMPLE_BY_ID.get(sample_id)
    if sample is None or not sample.path.is_file():
        raise HTTPException(status_code=404, detail="Sample invoice not found")
    return FileResponse(sample.path, media_type="application/pdf", filename=sample.filename)


DEMO_PAGE = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>VerityDocs invoice validation demo</title>
  <style>
    :root {
      color-scheme: light;
      --ink: #172638;
      --muted: #64748b;
      --line: #d9e2ec;
      --paper: #f5f7fa;
      --card: #ffffff;
      --blue: #2456a6;
      --blue-soft: #edf4ff;
      --green: #087a5c;
      --green-soft: #eaf8f3;
      --red: #ad3e45;
      --red-soft: #fff0f1;
      --amber: #9a671d;
      --amber-soft: #fff7e6;
      --navy: #14263b;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      background: var(--paper);
      color: var(--ink);
      font: 15px/1.5 system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }
    a { color: var(--blue); }
    button, input { font: inherit; }
    button { cursor: pointer; }
    .page { width: min(1120px, calc(100% - 36px)); margin: 0 auto; padding: 52px 0 32px; }
    .hero { display: flex; justify-content: space-between; gap: 28px; align-items: flex-end; margin-bottom: 28px; }
    .eyebrow, .rule-id, .metric-label, .field-meta, .evidence-label {
      color: var(--muted); font-size: 11px; letter-spacing: .08em; text-transform: uppercase;
    }
    h1, h2, h3, p { margin-top: 0; }
    h1 { margin-bottom: 10px; font-size: clamp(30px, 5vw, 48px); letter-spacing: -.045em; line-height: 1.05; }
    .lede { max-width: 640px; margin-bottom: 0; color: var(--muted); font-size: 16px; }
    .local-note { color: var(--muted); font-size: 12px; white-space: nowrap; }
    .panel, .result-panel { background: var(--card); border: 1px solid var(--line); border-radius: 16px; box-shadow: 0 12px 32px rgba(28, 48, 72, .05); }
    .panel { padding: 26px; }
    .input-grid { display: grid; grid-template-columns: minmax(0, 1.1fr) minmax(0, .9fr); gap: 26px; }
    .upload-box { border: 1px dashed #aebfd3; border-radius: 12px; padding: 22px; background: #fbfdff; }
    label { display: block; margin-bottom: 10px; font-weight: 650; }
    input[type=file] { width: 100%; padding: 12px; border: 1px solid var(--line); border-radius: 9px; background: white; }
    .hint, .sample-copy, .empty-copy { color: var(--muted); font-size: 13px; }
    .hint { margin: 10px 0 18px; }
    .primary-button, .sample-button { border: 0; border-radius: 9px; font-weight: 700; padding: 11px 15px; }
    .primary-button { background: var(--blue); color: white; }
    .primary-button:hover { background: #1c478c; }
    .primary-button:disabled, .sample-button:disabled { cursor: wait; opacity: .55; }
    .sample-heading { display: flex; justify-content: space-between; align-items: baseline; gap: 12px; margin-bottom: 12px; }
    .sample-heading h2, .result-heading h2, .card-heading h2 { margin-bottom: 0; font-size: 18px; letter-spacing: -.02em; }
    .sample-grid { display: grid; gap: 10px; }
    .sample-button { text-align: left; border: 1px solid var(--line); background: white; color: var(--ink); }
    .sample-button:hover { border-color: #7da3d5; background: var(--blue-soft); }
    .sample-title { display: block; font-weight: 700; }
    .sample-copy { display: block; margin-top: 3px; font-weight: 400; }
    .result-panel { margin-top: 22px; padding: 26px; }
    .empty-result { padding: 28px 4px 10px; }
    .empty-result h2 { margin-bottom: 8px; }
    .result-heading { display: flex; justify-content: space-between; gap: 18px; align-items: flex-start; border-bottom: 1px solid var(--line); padding-bottom: 20px; }
    .result-heading p { color: var(--muted); margin: 8px 0 0; overflow-wrap: anywhere; }
    .status { display: inline-flex; flex: none; align-items: center; border-radius: 999px; padding: 7px 10px; font-size: 11px; font-weight: 800; letter-spacing: .08em; }
    .status.pass { color: var(--green); background: var(--green-soft); }
    .status.fail { color: var(--red); background: var(--red-soft); }
    .status.unable { color: var(--amber); background: var(--amber-soft); }
    .result-grid { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, .95fr); gap: 16px; margin-top: 20px; }
    .card { border: 1px solid var(--line); border-radius: 12px; padding: 18px; background: #fff; }
    .card-heading { display: flex; justify-content: space-between; gap: 12px; align-items: baseline; margin-bottom: 14px; }
    .calculation { background: var(--navy); color: #f5f8fc; border-radius: 12px; padding: 18px; }
    .calculation .eyebrow, .calculation .metric-label { color: #a8bbd1; }
    .calculation h2 { margin: 6px 0 17px; font-size: 18px; }
    .equation { display: grid; grid-template-columns: 1fr auto 1fr auto 1fr; gap: 8px; align-items: end; }
    .equation span { color: #a8bbd1; font-size: 11px; }
    .equation strong { display: block; margin-top: 3px; font-size: 18px; }
    .equation .operator { color: #89a9d1; align-self: center; font-size: 22px; }
    .observed-total { border-top: 1px solid #34506f; margin-top: 16px; padding-top: 13px; display: flex; justify-content: space-between; gap: 10px; color: #a8bbd1; font-size: 12px; }
    .observed-total strong { color: white; font-size: 16px; }
    .check-list, .field-list { display: grid; gap: 10px; }
    .check { border: 1px solid var(--line); border-radius: 10px; padding: 13px; }
    .check.fail { border-color: #efc2c5; background: #fffafa; }
    .check.unable_to_verify { border-color: #ecd6a5; background: #fffdf7; }
    .check-top { display: flex; justify-content: space-between; gap: 8px; align-items: center; }
    .check-status { font-size: 10px; font-weight: 800; letter-spacing: .06em; }
    .check-status.pass { color: var(--green); }
    .check-status.fail { color: var(--red); }
    .check-status.unable_to_verify { color: var(--amber); }
    .check-message { margin: 8px 0 12px; font-weight: 600; }
    .metric-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 8px; }
    .metric { border-radius: 8px; background: #f7f9fb; padding: 9px; min-width: 0; }
    .metric-value { display: block; margin-top: 4px; overflow-wrap: anywhere; font-weight: 650; }
    .evidence-block { border-top: 1px solid var(--line); margin-top: 12px; padding-top: 11px; }
    .evidence-label { display: block; margin-bottom: 5px; }
    .evidence-line { margin: 4px 0; color: var(--muted); font-size: 12px; overflow-wrap: anywhere; }
    .evidence-line strong { color: var(--ink); font-weight: 650; }
    .field-row { border-bottom: 1px solid #edf1f5; padding: 11px 0; }
    .field-row:last-child { border-bottom: 0; padding-bottom: 0; }
    .field-top { display: flex; justify-content: space-between; gap: 14px; }
    .field-name { font-weight: 700; }
    .field-value { margin: 4px 0; overflow-wrap: anywhere; }
    .field-meta { font-size: 10px; letter-spacing: .02em; text-transform: none; }
    .error { border-color: #efc2c5; background: var(--red-soft); color: var(--red); }
    .error h2 { margin-bottom: 8px; }
    .error p { margin-bottom: 0; }
    .footer { padding: 22px 0 4px; text-align: center; color: var(--muted); font-size: 12px; }
    @media (max-width: 760px) {
      .page { width: min(100% - 24px, 680px); padding-top: 30px; }
      .hero { display: block; }
      .local-note { display: block; margin-top: 14px; white-space: normal; }
      .panel, .result-panel { padding: 17px; border-radius: 12px; }
      .input-grid, .result-grid { grid-template-columns: 1fr; gap: 18px; }
      .result-heading { display: block; }
      .result-heading .status { margin-top: 14px; }
      .equation { grid-template-columns: 1fr auto 1fr; }
      .equation .operator { grid-row: 2; }
      .equation strong { font-size: 16px; }
      .metric-grid { grid-template-columns: 1fr; }
    }
  </style>
</head>
<body>
  <main class="page">
    <header class="hero">
      <div>
        <div class="eyebrow">Local VerityDocs demo</div>
        <h1>Invoice validation</h1>
        <p class="lede">Upload an invoice PDF or image to run the existing OCR, extraction, evidence and deterministic financial-validation pipeline.</p>
      </div>
      <div class="local-note">Synthetic samples and local files only</div>
    </header>

    <section class="panel" aria-labelledby="input-heading">
      <div class="input-grid">
        <div class="upload-box">
          <form id="upload-form">
            <label id="input-heading" for="invoice-file">Invoice PDF or image</label>
            <input id="invoice-file" type="file" accept=".pdf,.png,.jpg,.jpeg,.webp,image/*,application/pdf">
            <p class="hint">Supported files: PDF, PNG, JPEG and WebP. The file is processed by this local server.</p>
            <button id="validate-button" class="primary-button" type="submit">Run validation</button>
          </form>
        </div>
        <div>
          <div class="sample-heading">
            <h2>Try a sample</h2>
            <span class="eyebrow">Synthetic invoices</span>
          </div>
          <div class="sample-grid">
            <button class="sample-button" data-sample="clean" type="button">
              <span class="sample-title">Clean sample</span>
              <span class="sample-copy">£8,000.00 + £1,600.00 = £9,600.00</span>
            </button>
            <button class="sample-button" data-sample="totals-mismatch" type="button">
              <span class="sample-title">Totals mismatch sample</span>
              <span class="sample-copy">Same inputs with a stated gross of £9,900.00</span>
            </button>
            <button class="sample-button" data-sample="missing-field" type="button">
              <span class="sample-title">Missing field sample</span>
              <span class="sample-copy">VAT is not stated on the document</span>
            </button>
          </div>
        </div>
      </div>
    </section>

    <section id="result-panel" class="result-panel" aria-live="polite" aria-busy="false">
      <div class="empty-result">
        <h2>Result state</h2>
        <p class="empty-copy">Run a sample or choose a local invoice to inspect extracted fields, financial totals, checks and source evidence.</p>
      </div>
    </section>

    <footer class="footer"><a href="https://github.com/ANKOHR/veritydocs">Demo of VerityDocs document validation</a></footer>
  </main>

  <script>
    (() => {
      const form = document.getElementById("upload-form");
      const fileInput = document.getElementById("invoice-file");
      const validateButton = document.getElementById("validate-button");
      const resultPanel = document.getElementById("result-panel");
      const sampleButtons = [...document.querySelectorAll("[data-sample]")];

      const escapeHtml = (value) => String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");

      const readableName = (value) => String(value || "")
        .replaceAll("_", " ")
        .replace(/\b\w/g, (letter) => letter.toUpperCase());

      const displayValue = (value) => {
        if (value === null || value === undefined || value === "") return "Not extracted";
        if (typeof value === "object") return JSON.stringify(value);
        return String(value);
      };

      const money = (value) => {
        if (value === null || value === undefined || value === "") return "Not produced";
        const amount = Number(value);
        if (!Number.isFinite(amount)) return displayValue(value);
        return new Intl.NumberFormat("en-GB", { style: "currency", currency: "GBP" }).format(amount);
      };

      const numeric = (value) => {
        if (value === null || value === undefined || value === "") return null;
        const amount = Number(value);
        return Number.isFinite(amount) ? amount : null;
      };

      const statusClass = (status) => {
        if (status === "PASS") return "pass";
        if (status === "FAIL") return "fail";
        return "unable";
      };

      const setBusy = (busy) => {
        validateButton.disabled = busy;
        sampleButtons.forEach((button) => { button.disabled = busy; });
        resultPanel.setAttribute("aria-busy", String(busy));
      };

      const showMessage = (title, message, className = "") => {
        resultPanel.innerHTML = `<div class="empty-result ${className}"><h2>${escapeHtml(title)}</h2><p>${escapeHtml(message)}</p></div>`;
      };

      const readError = async (response) => {
        try {
          const body = await response.json();
          return body.detail || body.message || "The document could not be processed.";
        } catch (_) {
          return "The document could not be processed.";
        }
      };

      const apiJson = async (url, options) => {
        const response = await fetch(url, options);
        if (!response.ok) throw new Error(await readError(response));
        return response.json();
      };

      const getField = (fields, name) => fields.find((field) => field.field_name === name);

      const evidenceForRule = (ruleId, fields) => {
        const names = {
          "FIN-001": ["net", "tax", "gross"],
          "RR-004": ["total_units"],
          "RR-007": ["reported_monthly_rent"],
          "OS-003": ["annual_revenue", "operating_expenses", "annual_noi"],
          "LOAN-001": ["loan_balance", "interest_rate"],
          "TAX-001": ["annual_property_tax"],
          "CON-001": ["contract_reference", "total_contract_value"],
          "PAY-001": ["contract_reference", "claimed_amount"]
        }[ruleId] || [];
        return fields.filter((field) => names.includes(field.field_name));
      };

      const renderEvidence = (fields) => {
        const lines = fields.flatMap((field) => (field.evidence || []).map((evidence) =>
          `<p class="evidence-line"><strong>${escapeHtml(readableName(field.field_name))}</strong> - page ${escapeHtml(evidence.page)}: ${escapeHtml(evidence.text)}</p>`
        ));
        if (lines.length === 0) return `<p class="evidence-line">No exact source span was produced for these fields.</p>`;
        return lines.join("");
      };

      const renderCheck = (check, fields) => {
        const expectedNumber = numeric(check.expected);
        const actualNumber = numeric(check.actual);
        const discrepancy = expectedNumber !== null && actualNumber !== null ? actualNumber - expectedNumber : null;
        const evidenceFields = evidenceForRule(check.rule_id, fields);
        const moneyRule = check.rule_id === "FIN-001" || ["RR-007", "OS-003", "TAX-001"].includes(check.rule_id);
        const formatCheckValue = (value) => moneyRule && numeric(value) !== null ? money(value) : displayValue(value);
        return `<article class="check ${escapeHtml(String(check.status).toLowerCase())}">
          <div class="check-top"><span class="rule-id">${escapeHtml(check.rule_id)}</span><span class="check-status ${escapeHtml(String(check.status).toLowerCase())}">${escapeHtml(check.status)}</span></div>
          <p class="check-message">${escapeHtml(check.message)}</p>
          <div class="metric-grid">
            <div class="metric"><span class="metric-label">Expected / calculated</span><span class="metric-value">${escapeHtml(formatCheckValue(check.expected))}</span></div>
            <div class="metric"><span class="metric-label">Observed / document</span><span class="metric-value">${escapeHtml(formatCheckValue(check.actual))}</span></div>
            <div class="metric"><span class="metric-label">Discrepancy</span><span class="metric-value">${escapeHtml(discrepancy === null ? "Not produced" : money(discrepancy))}</span></div>
          </div>
          <div class="evidence-block"><span class="evidence-label">Evidence for this check</span>${renderEvidence(evidenceFields)}</div>
        </article>`;
      };

      const renderCalculation = (fields, validations) => {
        const net = getField(fields, "net")?.value;
        const tax = getField(fields, "tax")?.value;
        const gross = getField(fields, "gross")?.value;
        const arithmetic = validations.find((check) => check.rule_id === "FIN-001");
        const expected = arithmetic ? arithmetic.expected : null;
        return `<div class="calculation">
          <div class="eyebrow">Financial totals</div>
          <h2>Validator calculation</h2>
          <div class="equation">
            <div><span>Net</span><strong>${escapeHtml(money(net))}</strong></div>
            <div class="operator">+</div>
            <div><span>VAT / tax</span><strong>${escapeHtml(money(tax))}</strong></div>
            <div class="operator">=</div>
            <div><span>Calculated gross</span><strong>${escapeHtml(money(expected))}</strong></div>
          </div>
          <div class="observed-total"><span>Observed / document gross</span><strong>${escapeHtml(money(gross))}</strong></div>
        </div>`;
      };

      const renderFields = (fields) => fields.map((field) => {
        const evidence = field.evidence || [];
        const evidenceText = evidence.length ? evidence.map((item) => `page ${item.page}: ${item.text}`).join(" | ") : "No exact source span";
        return `<div class="field-row">
          <div class="field-top"><span class="field-name">${escapeHtml(readableName(field.field_name))}</span><span class="field-meta">${escapeHtml(field.validation_status)}</span></div>
          <div class="field-value">${escapeHtml(displayValue(field.value))}</div>
          <div class="field-meta">${escapeHtml(field.method)} | evidence: ${escapeHtml(evidenceText)}</div>
        </div>`;
      }).join("");

      const renderResult = (view, filename) => {
        const validations = view.validations || [];
        const statuses = validations.map((check) => check.status);
        const overall = statuses.includes("FAIL") ? "FAIL" : statuses.includes("UNABLE_TO_VERIFY") ? "UNABLE TO VERIFY" : "PASS";
        const invoice = (view.documents || []).find((document) => document.document_type === "invoice") || view.documents?.[0];
        const fields = invoice?.fields || [];
        const flagged = validations.filter((check) => check.status !== "PASS").length;
        resultPanel.innerHTML = `<div class="result-heading">
          <div><div class="eyebrow">Validation result</div><h2>${escapeHtml(overall)}</h2><p>${escapeHtml(filename || invoice?.filename || "Uploaded document")}</p></div>
          <span class="status ${statusClass(overall === "UNABLE TO VERIFY" ? "UNABLE" : overall)}">${escapeHtml(overall)}</span>
        </div>
        <div class="result-grid">
          <div>${renderCalculation(fields, validations)}
            <div class="card" style="margin-top:16px"><div class="card-heading"><h2>Validation checks</h2><span class="field-meta">${flagged} flagged</span></div><div class="check-list">${validations.map((check) => renderCheck(check, fields)).join("")}</div></div>
          </div>
          <div class="card"><div class="card-heading"><h2>Extracted fields</h2><span class="field-meta">${fields.length} fields</span></div><div class="field-list">${fields.length ? renderFields(fields) : '<p class="empty-copy">No fields were extracted.</p>'}</div></div>
        </div>`;
      };

      const createAndUpload = async (file, sourceLabel) => {
        const created = await apiJson("/api/cases", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ name: `Invoice demo - ${sourceLabel}` })
        });
        const body = new FormData();
        body.append("file", file, file.name);
        await apiJson(`/api/cases/${encodeURIComponent(created.id)}/documents?run_pipeline=true`, { method: "POST", body });
        return apiJson(`/api/cases/${encodeURIComponent(created.id)}`);
      };

      const runFile = async (file, sourceLabel) => {
        if (!file) {
          showMessage("Choose a document", "Select an invoice PDF or image before running validation.");
          return;
        }
        setBusy(true);
        showMessage("Processing document", "The local OCR and validation pipeline is running.");
        try {
          const view = await createAndUpload(file, sourceLabel);
          renderResult(view, file.name);
        } catch (error) {
          showMessage("Could not process document", error instanceof Error ? error.message : "The document could not be processed.", "error");
        } finally {
          setBusy(false);
        }
      };

      form.addEventListener("submit", (event) => {
        event.preventDefault();
        runFile(fileInput.files[0], "uploaded file");
      });

      sampleButtons.forEach((button) => {
        button.addEventListener("click", async () => {
          const sampleId = button.dataset.sample;
          const sampleTitle = button.querySelector(".sample-title")?.textContent || "synthetic sample";
          setBusy(true);
          showMessage("Loading sample", "The synthetic invoice is being sent through the local pipeline.");
          try {
            const response = await fetch(`/demo/samples/${encodeURIComponent(sampleId)}`);
            if (!response.ok) throw new Error(await readError(response));
            const blob = await response.blob();
            const file = new File([blob], `veritydocs-${sampleId}.pdf`, { type: "application/pdf" });
            const view = await createAndUpload(file, sampleTitle);
            renderResult(view, file.name);
          } catch (error) {
            showMessage("Could not process sample", error instanceof Error ? error.message : "The sample could not be processed.", "error");
          } finally {
            setBusy(false);
          }
        });
      });
    })();
  </script>
</body>
</html>"""
