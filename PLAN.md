# Document Intelligence Pipeline with n8n — Project Plan

> Vision-LLM document extraction pipeline for automotive dealership paperwork (invoices, ID cards, sales orders), orchestrated by self-hosted n8n on a 1GB VPS.

**Owner:** Ahmad
**Target duration:** ~2 weeks
**Purpose:** Portfolio project for an AI Engineer role (n8n + LLM APIs + Python + automation)

---

## 1. Goals

### Primary goals
- Extract structured data (JSON) from unstructured documents using a vision LLM.
- Validate extracted data against a strict schema and business rules.
- Flag anomalies and incomplete documents automatically.
- Run reliably on a **1GB RAM VPS** using self-hosted n8n.

### Portfolio goals
- Demonstrate: LLM API usage, structured output, validation, error handling, evaluation, deployment.
- Produce measurable results (field-level accuracy, latency, cost per document).
- Ship with clear documentation, an architecture diagram, and a 1–2 minute demo video.

### Non-goals
- No local OCR or local LLM inference on the VPS.
- No real personal data. **Synthetic/dummy documents only.**
- No production-grade multi-tenant system.

---

## 2. Use Case

A dealership staff member (or customer) uploads a document via Telegram or a web form. The pipeline:

1. Classifies the document type.
2. Extracts the relevant fields.
3. Validates the output.
4. Stores clean data and notifies staff about problems.

### Supported document types

| Type | Example fields |
|---|---|
| Invoice | invoice_number, date, vendor, line_items, subtotal, tax, total |
| ID card (KTP, synthetic) | nik, name, birth_date, address, gender |
| Sales order (SPK, synthetic) | spk_number, customer_name, model, variant, color, price, payment_method |
| Salary slip (synthetic, optional) | employee_name, period, gross_salary, net_salary |

---

## 3. Architecture

```
┌──────────────┐    ┌───────────────────────────────────────────────────┐
│ Telegram Bot │──▶ │                  n8n (VPS, Docker)                │
│ / Webhook    │    │                                                   │
└──────────────┘    │  1. Intake & file checks                          │
                    │  2. Pre-process (PDF → images, resize)            │
                    │  3. Classify document type  ──▶ Vision LLM API    │
                    │  4. Extract fields (typed prompt + JSON schema)   │
                    │  5. Validate (schema + business rules)            │
                    │  6. Route: OK / Needs review / Failed             │
                    └──────────────┬──────────────────┬─────────────────┘
                                   │                  │
                       ┌───────────▼───────┐  ┌───────▼─────────────┐
                       │   Google Sheets   │  │ Telegram notification│
                       │ (clean data, logs)│  │ (review / alerts)    │
                       └───────────────────┘  └──────────────────────┘
```

### Design principles
- **VPS is only an orchestrator.** All heavy inference happens through APIs.
- **One document at a time** to stay within memory limits.
- **Everything is validated.** The LLM output is never trusted blindly.
- **Everything is logged.** Cost, latency, and outcome per document.

---

## 4. Tech Stack

| Layer | Choice | Notes |
|---|---|---|
| Orchestration | n8n (self-hosted, Docker) | SQLite, filesystem binary mode |
| LLM | Claude (vision) primary; GPT/Gemini as fallback | Structured JSON output |
| Validation | n8n Code node (JS) + optional Python FastAPI service | JSON Schema, regex, checksum rules |
| Storage | Google Sheets (final database) | External, not on VPS; accessed via n8n Google Sheets node |
| Intake / Notify | Telegram Bot API | Free, simple |
| Reverse proxy | Caddy | Automatic HTTPS |
| Evaluation | Python script + labeled dataset | Runs locally, results in README |
| Observability | Log table (tokens, cost, latency, status) | Optional Langfuse |

---

## 5. n8n Workflows

### WF-01 — Intake
- **Trigger:** Telegram message with file / Webhook.
- Check file type (PDF, JPG, PNG) and size (≤ 5MB, ≤ 10 pages).
- Reject invalid files with a clear message.
- Append a row to the `documents` sheet with status `received`.

### WF-02 — Pre-process
- PDF → page images (resize to a max width, e.g. 1600px).
- Strip unneeded metadata.
- Save binary to filesystem (not memory).

### WF-03 — Classify
- Send the first page to the LLM: "Which document type is this?"
- Output: `{ "type": "invoice | ktp | spk | other", "confidence": 0-1 }`.
- Confidence below threshold → `needs_review`.

### WF-04 — Extract
- Select the prompt and JSON schema by document type.
- Call the vision LLM with the image(s) and schema instructions.
- Parse and store the raw JSON output.
- Retry once on malformed JSON; fall back to a secondary model on repeated failure.

### WF-05 — Validate
- **Schema validation:** required fields, data types, formats.
- **Business rules**, examples:
  - Invoice: `sum(line_items) + tax == total` (within tolerance).
  - NIK: 16 digits, valid date segment, consistent with birth_date and gender.
  - SPK: price within the expected range for the model/variant.
  - Dates not in the future; expired documents flagged.
- Output: `valid`, `warnings[]`, `errors[]`.

### WF-06 — Route & Notify
- `valid` → write to the `extractions` sheet → confirm to the user.
- `warnings` → write + flag for human review (Telegram with inline approve/reject).
- `errors` → status `failed`, reason sent to the user.

### WF-07 — Error handler (global)
- Catches workflow failures, logs them, and alerts via Telegram.

### WF-08 — Weekly report (optional)
- Summarize volume, accuracy proxy, flagged rate, cost; send to Telegram/email.

---

## 6. Data Model (Google Sheets)

One spreadsheet, **`DocIntel_DB`**, with one tab per table. Row 1 holds column headers; n8n appends/updates rows by `id` using the Google Sheets node (service account credentials, spreadsheet shared with the service account email).

### Tab `documents`
| Column | Type | Notes |
|---|---|---|
| id | string (uuid) | Row key, generated in n8n |
| source | string | telegram / webhook |
| doc_type | string | invoice / ktp / spk / other |
| status | string | received / extracted / valid / needs_review / failed |
| confidence | number | Classification confidence |
| created_at | ISO datetime | |

### Tab `extractions`
| Column | Type | Notes |
|---|---|---|
| id | string (uuid) | Row key |
| document_id | string | Reference to `documents.id` |
| data | JSON string | Extracted fields |
| warnings | JSON string | Validation warnings |
| errors | JSON string | Validation errors |
| model | string | Model used |

### Tab `run_logs`
| Column | Type | Notes |
|---|---|---|
| id | string (uuid) | Row key |
| document_id | string | Reference to `documents.id` |
| step | string | classify / extract / validate |
| tokens_in / tokens_out | number | |
| cost_usd | number | |
| latency_ms | number | |

### Google Sheets constraints and mitigations
- **API quota (~60 requests/min per user):** write one batched row per step, not per field; add a short Wait node if needed.
- **No transactions or foreign keys:** `document_id` is only a convention; n8n enforces consistency.
- **Cell size limit (50,000 chars):** store compact JSON; never store base64 images in cells.
- **Concurrent writes:** documents are processed sequentially, which avoids row conflicts.
- **Scale:** fine for demo-level volume (thousands of rows). Migrating to Postgres later only requires replacing the Sheets nodes.

---

## 7. VPS Deployment (1GB RAM)

### Baseline setup
- Ubuntu LTS, Docker + Docker Compose, UFW (ports 22/80/443 only).
- **2GB swap file** (mandatory).
- Caddy for HTTPS, n8n bound to `127.0.0.1:5678`.

### Key n8n environment settings
```yaml
- N8N_DEFAULT_BINARY_DATA_MODE=filesystem
- EXECUTIONS_DATA_PRUNE=true
- EXECUTIONS_DATA_MAX_AGE=72
- EXECUTIONS_DATA_SAVE_ON_SUCCESS=none
- NODE_OPTIONS=--max-old-space-size=512
- GENERIC_TIMEZONE=Asia/Jakarta
```
Container memory limit: ~700MB.

### Operational rules
- Process documents sequentially (Split In Batches / concurrency limit).
- File limits enforced at intake.
- Weekly backup of `n8n_data`; export workflows to Git.
- Secrets in n8n credentials / `.env`, never committed.

---

## 8. Evaluation Plan

### Dataset
- 30 synthetic documents per type (≈100 total), generated from templates with varied layouts, fonts, noise, rotation, and blur.
- Ground-truth JSON for every document.

### Metrics

| Metric | Definition |
|---|---|
| Field-level accuracy | Correct fields / total fields |
| Document-level exact match | Documents with all fields correct |
| Classification accuracy | Correct doc type / total |
| Validation precision/recall | Whether injected errors (wrong totals, bad NIK) get flagged |
| Latency | Median and p95 per document |
| Cost | USD per document |

### Experiments
1. Prompt v1 vs v2 (with/without few-shot examples).
2. Primary model vs fallback model.
3. Image resolution vs accuracy/cost trade-off.

Results are reported in a table in the README.

---

## 9. Timeline & Phases

The project is split into 4 phases (~14 days).

### Phase 1 — Foundation (Days 1–4)
**Goal:** infrastructure is ready and test data exists.
- Set up the VPS: Docker, Caddy (HTTPS), 2GB swap, UFW, and n8n with memory-saving config.
- Create the Telegram bot and the Google Sheets service account (`DocIntel_DB` with tabs `documents`, `extractions`, `run_logs`).
- Write JSON schemas for invoice, KTP, and SPK.
- Build the synthetic document generator and ground truth (`generate_docs.py`) with layout, noise, rotation, and blur variations.

**Done when:** n8n is reachable over HTTPS, the bot replies, and a synthetic dataset with ground truth is available.

### Phase 2 — Core Pipeline (Days 5–9)
**Goal:** a document goes in and comes out as clean data, end-to-end.
- Build WF-01 to WF-04: intake, pre-process, classify, extract.
- Build WF-05 and WF-06: validation (schema + business rules), routing (OK / review / failed), and Telegram notifications.
- Add reliability: malformed-JSON retry, fallback model, global error handler (WF-07), and token/cost/latency logging.
- Prioritize **invoice and KTP** first; SPK follows.

**Done when:** 3 document types are processed end-to-end and failures are handled with clear messages.

### Phase 3 — Evaluation & Optimization (Days 10–12)
**Goal:** measurable results and a stable system.
- Build `run_eval.py` to compute field accuracy, exact match, classification accuracy, validation recall, latency, and cost.
- Run experiments: prompt v1 vs v2, primary vs fallback model, image resolution.
- Iterate prompts based on the most frequent errors; tune memory, concurrency limits, and cost.
- Run a 48-hour stability test.

**Done when:** the evaluation results table exists and the VPS is stable with no OOM.

### Phase 4 — Documentation & Demo (Days 13–14)
**Goal:** the project is ready to showcase.
- Write the README: architecture diagram, setup, and results table.
- Export workflows, schemas, and prompts to the repo (no secrets).
- Record the 1–2 minute demo video and finalize the CV bullet with real numbers.

**Done when:** every item in the Definition of Done (section 12) is met.

### Cut list (if time is short)
SPK, WF-08 (weekly report), salary slip, and the image-resolution experiment.

---

## 10. Repository Structure

```
document-intelligence-n8n/
├── README.md
├── docs/
│   ├── architecture.png
│   └── evaluation.md
├── infra/
│   ├── docker-compose.yml
│   ├── Caddyfile
│   └── .env.example
├── workflows/
│   ├── 01-intake.json
│   ├── 02-preprocess.json
│   ├── 03-classify.json
│   ├── 04-extract.json
│   ├── 05-validate.json
│   ├── 06-route-notify.json
│   └── 07-error-handler.json
├── schemas/
│   ├── invoice.schema.json
│   ├── ktp.schema.json
│   └── spk.schema.json
├── prompts/
│   ├── classify.md
│   └── extract_*.md
├── data/
│   ├── synthetic/          # dummy documents
│   └── ground_truth/
└── eval/
    ├── generate_docs.py
    ├── run_eval.py
    └── results.md
```

---

## 11. Risks & Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Out of memory on 1GB VPS | Crashes | Swap, filesystem binary mode, memory limits, sequential processing |
| LLM hallucinated fields | Wrong data | Strict schema, business-rule validation, human review path |
| API cost growth | Budget | Image downscaling, cost logging, daily cap |
| Malformed JSON output | Pipeline errors | Schema-constrained output, retry, fallback model |
| Privacy concerns | Ethical/legal | Synthetic data only, clear "demo" labeling, no real PII in repo |
| Scope creep | Delays | Ship invoice + KTP first; SPK and extras are optional |

---

## 12. Definition of Done

- [ ] n8n running on the VPS over HTTPS, stable for 48h.
- [ ] Three document types processed end-to-end.
- [ ] Validation catches injected errors with measurable recall.
- [ ] Evaluation results documented (accuracy, latency, cost).
- [ ] Workflows, schemas, and prompts exported to the repo.
- [ ] README with architecture diagram and setup instructions.
- [ ] Demo video recorded.
- [ ] Data is synthetic; no secrets in the repo.

---

## 13. CV Bullet (draft)

> Built a vision-LLM document intelligence pipeline in n8n for dealership paperwork (invoices, ID cards, sales orders) with JSON-schema and business-rule validation, human-in-the-loop review, and cost/latency logging; self-hosted on a 1GB VPS (Docker, Caddy, swap and memory tuning). Achieved X% field-level accuracy and Y% error-detection recall on a 100-document synthetic benchmark at ~$Z per document.

---

## 14. Possible Extensions

- Python FastAPI microservice for advanced validation and fuzzy matching.
- Duplicate document detection (hashing / embeddings).
- Simple dashboard (Streamlit/Metabase) over the Google Sheets data (Looker Studio is a free option).
- Migrate storage from Google Sheets to Postgres/Supabase if volume grows.
- Integration with the Sales & Service Assistant project (documents feed lead records).
