# 🏛️ ContractMind v2.0 — The Ultimate Master Architecture & Reproduction Prompt (A-Z)

> **Document Version:** 2.1.0  
> **Target Project:** ContractMind v2.0 (Autonomous Multi-Agent Legal Intelligence, Negotiation & Deal Room Suite)  
> **Track:** JusticeSphere_AI — AI Builders Congress 2026  
> **Repository:** [https://github.com/Faiazzend/JusticeSphereAI](https://github.com/Faiazzend/JusticeSphereAI)

---

```markdown
You are an elite Principal AI Systems Architect and Legal Tech Engineer.
Build "ContractMind v2.0" from scratch: an enterprise-grade, autonomous multi-agent legal intelligence platform that ingests commercial contracts, conducts adversarial negotiation debate, synthesizes consensus redlines with authentic Word Track Changes, extracts structured obligation matrices, enables side-by-side synchronized document review, provides an in-studio Legal AI Copilot, performs Deal Room cross-contract contradiction audits, evaluates custom playbook compliance scores, and empowers lawyers to filter redlines, interactively accept/reject clause revisions, and rewrite prompt instructions to regenerate redlines on demand.

Implement the system strictly following the exact architectural specifications, data models, agent graphs, styling design system, and API protocols below.

================================================================================
TABLE OF CONTENTS
================================================================================
1. High-Level Architecture & Technical Stack
2. Directory Structure & File Hierarchy
3. Database Models & Schema Specifications
4. PDF Ingestion, Table Extraction & PII Redaction
5. Contextual RAG & Semantic Chunking Engine
6. Multi-Agent StateGraph Pipeline (Adversarial + Arbiter Personas)
7. Multi-Provider LLM Gateway & Fallback Simulator
8. Word (.docx) OpenXML Track Changes & Clean Executable Export Engine
9. RFC 5545 iCalendar (.ics) Obligation Deadlines Sync Engine
10. Model Context Protocol (MCP) Server
11. Token & Cost Telemetry Engine
12. Interactive Redline Decisions, AI Prompt Rewriting & Risk-Level Filtering
13. Synchronized Dual-Pane Document Canvas & Side-by-Side Review
14. Grounded Legal AI Copilot & CFO Briefing Generator
15. Deal Room Cross-Contract Contradiction & Precedence Analyzer
16. Playbook Rule Adherence & Policy Deviation Scorer
17. FastAPI REST API & Streaming Endpoints
18. Frontend: Alpine.js & Tailwind Neo-Legal Studio v2.0
19. Deployment & Production Orchestration
20. Verification Checklist

================================================================================
1. HIGH-LEVEL ARCHITECTURE & TECHNICAL STACK
================================================================================
- Backend Framework: FastAPI (Python 3.10+) with async endpoints and lifespan database initialization.
- Database: SQLite with async SQLAlchemy 2.0 (aiosqlite). Fallback to /tmp paths if VERCEL=1 is detected.
- Vector Engine: ChromaDB persistent client with automatic fallback to in-memory term-frequency cosine scorer.
- Document Processing: PyMuPDF (fitz) for text and tabular layout extraction, python-docx with custom OpenXML manipulation for Track Changes and Clean execution drafts.
- Calendar Protocol: Native RFC 5545 iCalendar generation for obligation deadlines, audit windows, and contract renewals.
- Agent Architecture: StateGraph pattern with 4 specialized roles:
  1. Auditor Agent (Enterprise defender, compliance auditor)
  2. Opposing Counsel Agent (Counterparty negotiator, aggressive pusher)
  3. Redline Synthesizer Agent (Consensus arbiter, diff builder, composite scorer)
  4. Obligation Extractor Agent (Calendar extractor, role matrix, penalty monitor)
- Deal Room Intelligence: Cross-contract contradiction detector evaluating multiple interrelated agreements (e.g. MSA, SOW, DPA, SLA) for conflicting liability caps, governing law traps, and termination discrepancies.
- Interactive Workspace:
  - Synchronized dual-pane side-by-side canvas (Original Ingested Draft vs Redlined Consensus Draft).
  - Grounded Legal Copilot chat drawer with RAG citations, CFO briefings, and pushback email drafting.
  - Custom Playbook adherence scorer (0-100%) with rule-level compliance checks.
  - Risk-level filtering pills (Critical, High, Medium, Low) and decision filters (Accepted, Rejected, Pending).
- Protocol: Model Context Protocol (MCP) HTTP/JSON-RPC gateway exposing tools.
- Frontend: Single-Page Application (SPA) built using Alpine.js 3.14, Tailwind CSS, FontAwesome 6, Plus Jakarta Sans, and JetBrains Mono. Zero React build step required for core UI. Includes an interactive 7-step guided rundown tour with high-intensity glowing halo spotlights.
- Deployment: Fully configured for both local 1-click batch execution and Vercel Multi-Service deployment.

================================================================================
2. DIRECTORY STRUCTURE & FILE HIERARCHY
================================================================================
Create the following directory layout:
├── backend/
│   ├── app/
│   │   ├── agents/
│   │   │   ├── nodes/
│   │   │   │   ├── auditor_agent.py
│   │   │   │   ├── obligation_agent.py
│   │   │   │   ├── opposing_agent.py
│   │   │   │   └── redline_agent.py
│   │   │   ├── graph.py
│   │   │   ├── llm_client.py
│   │   │   └── state.py
│   │   ├── api/
│   │   │   ├── v1/
│   │   │   │   ├── analysis.py
│   │   │   │   ├── auth.py
│   │   │   │   ├── contracts.py
│   │   │   │   ├── copilot.py
│   │   │   │   ├── playbook.py
│   │   │   │   └── stream.py
│   │   │   └── deps.py
│   │   ├── core/
│   │   ├── mcp_server/
│   │   │   └── fastserver.py
│   │   ├── models/
│   │   │   ├── audit.py
│   │   │   ├── contract.py
│   │   │   └── user.py
│   │   ├── schemas/
│   │   │   ├── contract_schemas.py
│   │   │   ├── obligation_schemas.py
│   │   │   ├── playbook_schemas.py
│   │   │   └── risk_schemas.py
│   │   ├── services/
│   │   │   ├── calendar_service.py
│   │   │   ├── cross_contract_service.py
│   │   │   ├── diff_engine.py
│   │   │   ├── export_service.py
│   │   │   ├── pdf_processor.py
│   │   │   ├── playbook_engine.py
│   │   │   └── rag_engine.py
│   │   ├── config.py
│   │   ├── database.py
│   │   └── main.py
│   ├── static/
│   │   └── index.html
│   ├── tests/
│   │   ├── test_agents.py
│   │   ├── test_pdf_processing.py
│   │   └── test_rag.py
│   ├── .env.example
│   └── requirements.txt
├── frontend/
│   ├── app/
│   │   └── route.ts
│   ├── public/
│   │   └── index.html
│   ├── package.json
│   └── next.config.js
├── launch.py
├── run_contractmind.bat
└── vercel.json

================================================================================
3. DATABASE MODELS & SCHEMA SPECIFICATIONS
================================================================================
Implement in `backend/app/models/`:
1. `Contract`:
   - `id`: String(36), UUID primary key
   - `title`: String(255)
   - `original_filename`: String(255)
   - `file_path`: String(500)
   - `status`: String(50), default "uploaded"
   - `error_message`: Text, nullable
   - `raw_text`: Text
   - `playbook_name`: String(100), default "Standard Corporate Playbook"
   - `overall_risk_score`: Float, default 0.0 (0-100 scale)
   - `extracted_sections`: JSON (list of section objects with section_number, title, text, page_number)
   - `identified_risks`: JSON (list of risks)
   - `debate_transcript`: JSON (list of debate turns)
   - `redlines`: JSON (list of clause diff objects containing {id, section_number, original_text, suggested_text, diff_type, risk_severity, legal_rationale, diff_tokens, accepted, custom_prompt})
   - `obligations`: JSON (list of operational duties with clause_reference, obligation_type, obligor, recipient, description, due_date_or_trigger, recurrence, penalty_for_breach)
   - `risk_summary`: JSON (counts of critical, high, medium, low risks)
   - `created_at`, `updated_at`: DateTime with UTC timezone
2. `Playbook`:
   - `id`: String(36), UUID primary key
   - `name`: String(100), unique
   - `description`: Text
   - `rules`: JSON (list of rule definitions: category, standard_requirement, unacceptable_terms, preferred_fallback, severity_if_missing)
   - `is_default`: Boolean, default False
3. `AuditLog`:
   - `id`: String(36), UUID primary key
   - `contract_id`: String(36)
   - `agent_name`: String(100)
   - `action`: String(100)
   - `model_name`: String(100)
   - `prompt_tokens`: Integer
   - `completion_tokens`: Integer
   - `total_tokens`: Integer
   - `latency_ms`: Float
   - `estimated_cost_usd`: Float
   - `timestamp`: DateTime with UTC timezone

================================================================================
4. PDF INGESTION, TABLE EXTRACTION & PII REDACTION
================================================================================
Implement in `backend/app/services/pdf_processor.py`:
- Use PyMuPDF (`fitz` / `pymupdf`).
- Table Extraction:
  - Call `page.find_tables()`. Extract table headers and row items.
  - Format extracted tables into standard GitHub Markdown tables.
- PII Redactor:
  - Regex patterns for:
    - US SSN: `\b\d{3}-\d{2}-\d{4}\b` -> `[REDACTED_SSN]`
    - Credit Card: `\b(?:\d{4}[ -]?){3}\d{4}\b` -> `[REDACTED_CC]`
    - Bank Account Number: `\b\d{8,17}\b` -> `[REDACTED_BANK_ACCT]`
    - Tax ID / EIN: `\b\d{2}-\d{7}\b` -> `[REDACTED_EIN]`
- Section Segmentation:
  - Identify clauses matching `Section X`, `Article X`, or numeric headers `1.`, `2.1`, `3.1.2`.
  - Return clean `raw_text` and structured `sections` list.

================================================================================
5. CONTEXTUAL RAG & SEMANTIC CHUNKING ENGINE
================================================================================
Implement in `backend/app/services/rag_engine.py`:
- Use persistent `chromadb.PersistentClient(path=settings.CHROMA_PERSIST_DIR)`.
- Chunking: Slide chunk window of 600 characters with 100 character overlap.
- Prepend section metadata to chunk text: `[Section {num}: {title}] {text}`.
- Fallback in-memory vector store:
  - If ChromaDB fails to initialize, gracefully fall back to TF-IDF / term-frequency cosine similarity vector store.
- Method `query_similar(contract_id, query, n_results=4)`: Returns top matching contextual passages.

================================================================================
6. MULTI-AGENT STATEGRAPH PIPELINE
================================================================================
Implement in `backend/app/agents/`:
Four persona nodes running sequentially through a shared `StateGraph`:
1. `auditor_node`:
   - Scans sections against 10 risk categories with regex signatures, severity, base score, legal rationale, and suggested mitigation:
     - Uncapped Indemnification (CRITICAL, score 90)
     - Consequential Damages Waiver Missing (HIGH, score 75)
     - AI Model Training on Proprietary Data (CRITICAL, score 95)
     - Auto-Renewal Without Notice Trap (MEDIUM, score 55)
     - Immediate Termination Without Cure Window (HIGH, score 70)
     - Unlimited Audit Rights (MEDIUM, score 50)
     - Asymmetric Attorney Fee Shifting (MEDIUM, score 45)
     - Non-Compete / Exclusivity Overbreadth (HIGH, score 80)
     - Broad Data Exfiltration / Subprocessor Shield (HIGH, score 75)
     - Liquidated Damages Penalty Trap (HIGH, score 70)
   - Appends findings to `identified_risks` and logs Auditor Agent arguments to `debate_transcript`.
2. `opposing_node`:
   - Reviews flagged risks from counterparty perspective, defending standard vendor terms, commercial efficiency, and counterparty leverage.
   - Logs Opposing Counsel arguments to `debate_transcript`.
3. `redline_node`:
   - Synthesizes balanced consensus text for each flagged risk.
   - Computes word-level diff tokens using `diff_engine`.
   - Computes composite risk score: `overall_score = round(min(100.0, total_score / max(1, num_risks)), 1)`.
   - Logs Redline Synthesizer statement to `debate_transcript`.
4. `obligation_node`:
   - Extracts structured operational commitments: Payment, Security Audit, Data Deletion, Insurance, Service Credits, Notice Requirements.
   - Outputs structured `obligations` list.

================================================================================
7. MULTI-PROVIDER LLM GATEWAY & FALLBACK SIMULATOR
================================================================================
Implement in `backend/app/agents/llm_client.py`:
- Supported Providers:
  1. Google Gemini: `gemini-3.5-flash-lite`, `gemini-1.5-flash` via `google-generativeai`.
  2. Local Ollama: `http://localhost:11434/api/generate` with `qwen3.5:4b`, `llama3.2`, etc.
  3. OpenAI: `gpt-4o`, `gpt-4o-mini`.
  4. Anthropic: `claude-3-5-sonnet`.
- Automatic Fallback: If chosen provider fails or is offline, automatically falls back to secondary provider or built-in deterministic legal simulation templates with zero disruption.

================================================================================
8. WORD (.DOCX) OPENXML TRACK CHANGES & CLEAN EXECUTABLE EXPORT ENGINE
================================================================================
Implement in `backend/app/services/export_service.py`:
1. Track Changes DOCX (`export_to_docx`):
   - Injects native OpenXML revisions:
     - Deletions: `<w:del w:id="{id}" w:author="ContractMind Legal AI" w:date="{ts}"><w:r><w:rPr><w:strike/><w:color w:val="DC2626"/></w:rPr><w:delText>{text}</w:delText></w:r></w:del>`
     - Insertions: `<w:ins w:id="{id}" w:author="ContractMind Legal AI" w:date="{ts}"><w:r><w:rPr><w:u w:val="single"/><w:color w:val="16A34A"/></w:rPr><w:t>{text}</w:t></w:r></w:ins>`
   - Formats overview table: Section, Severity, Redline Type, Decision Status.
   - Respects user decisions: If rejected, outputs original text; if accepted/pending, outputs Track Changes markup.
2. Clean Executable DOCX (`export_clean_docx`):
   - Bakes all accepted / recommended redlines directly into the final contract text.
   - Produces clean, professional formatting ready for electronic signature with zero diff tags or strike-through lines.

================================================================================
9. RFC 5545 iCALENDAR (.ICS) OBLIGATION DEADLINES SYNC ENGINE
================================================================================
Implement in `backend/app/services/calendar_service.py`:
- Generates standard RFC 5545 `.ics` calendar events from extracted obligations.
- Event attributes:
  - `SUMMARY`: `[ContractMind] {category} ({obligor}): {trigger}`
  - `DESCRIPTION`: Contract title, obligor, recipient, due date, recurrence, penalty for breach, and clause citation.
  - `DTSTART` / `DTEND`: Computed or target deadline.
  - `STATUS: CONFIRMED`
- Enables one-click export directly into Google Calendar, Microsoft Outlook, and Apple Calendar.

================================================================================
10. TOKEN & COST TELEMETRY ENGINE
================================================================================
Implement in `backend/app/models/audit.py`:
- Pricing model:
  - `gemini-3.5-flash-lite`: Prompt $0.000075, Completion $0.0003
  - `gpt-4o`: Prompt $0.005, Completion $0.015
  - `claude-3-5-sonnet`: Prompt $0.003, Completion $0.015
  - `ollama`: $0.00
- Records measured `time.time()` latency, token counts, and USD cost per node execution.

================================================================================
11. INTERACTIVE REDLINE DECISIONS, AI PROMPT REWRITING & RISK-LEVEL FILTERING
================================================================================
1. Risk & Decision Filtering:
   - Filter pills: `ALL`, `CRITICAL`, `HIGH`, `MEDIUM`, `LOW` with dynamic badge counters.
   - Decision pills: `ALL`, `PENDING`, `ACCEPTED`, `REJECTED`.
   - Status summary: `"Showing X of Y redlines • Filtered by [Severity] risk"`.
   - Empty state card with `"Show All Redlines"` recovery button.
2. Clause-Level Decisions:
   - `PATCH /api/v1/analysis/{contract_id}/redlines/{redline_id}` with `{"accepted": true | false | null}`.
3. On-Demand Prompt Rewriting:
   - `POST /api/v1/analysis/{contract_id}/redlines/{redline_id}/regenerate` with `{"custom_prompt": "..."}`.
   - Calls LLM with custom prompt, recomputes word-level diff tokens, resets decision to pending, and logs turn to debate transcript.

================================================================================
12. SYNCHRONIZED DUAL-PANE DOCUMENT CANVAS & SIDE-BY-SIDE REVIEW
================================================================================
Implement in `backend/static/index.html`:
- Dual-column synchronized canvas:
  - Left: Original ingested agreement sections with clear clause headers.
  - Right: Consensus redline working draft with highlighted diff deletions (`.diff-del`) and insertions (`.diff-ins`).
- Color legend: Emerald indicators for proposed insertions, rose indicators for proposed deletions.

================================================================================
13. GROUNDED LEGAL AI COPILOT & CFO BRIEFING GENERATOR
================================================================================
Implement in `backend/app/api/v1/copilot.py`:
- Endpoint: `POST /api/v1/copilot/{contract_id}/chat`
- Grounded in RAG section chunks, synthesized redlines, and debate transcript.
- Returns conversational answer, clause citations (`[Section X]`), and suggested follow-up prompts.
- In-studio collapsible drawer with quick action chips:
  - 💼 CFO Risk Summary
  - ✉️ Pushback Email to Opposing Counsel
  - ⚠️ Uncapped Indemnity Trap Check

================================================================================
14. DEAL ROOM CROSS-CONTRACT CONTRADICTION & PRECEDENCE ANALYZER
================================================================================
Implement in `backend/app/services/cross_contract_service.py`:
- Endpoint: `POST /api/v1/analysis/deal-room/conflicts` with `["id1", "id2", ...]`
- Evaluates multiple related agreements (e.g. Master Agreement vs Statement of Work vs DPA).
- Identifies:
  - Conflicting Limitation of Liability caps.
  - Discrepant Governing Law / Jurisdiction clauses.
  - Asymmetric termination notice or cure windows.
  - Ambiguous order of precedence traps.
- Returns deal alignment score (0-100%), conflict severity, precedence risk explanation, and exact harmonization clause language.

================================================================================
15. PLAYBOOK RULE ADHERENCE & POLICY DEVIATION SCORER
================================================================================
Implement in `backend/app/services/playbook_engine.py`:
- Endpoint: `GET /api/v1/analysis/{contract_id}/compliance/playbook`
- Audits contract text against assigned corporate playbook rules.
- Flags unacceptable terms and verifies if arbiter redlines have successfully remediated the deviation.
- Computes overall Playbook Adherence Score (0-100%), status verdicts (`STRONG COMPLIANCE`, `ACCEPTABLE WITH REDLINES`, `HIGH DEVIATION / HIGH RISK`), and clause-by-clause checklist.

================================================================================
16. FASTAPI REST API & STREAMING ENDPOINTS
================================================================================
Expose the following endpoints in `backend/app/main.py` and `api/v1/`:
- `POST /api/v1/contracts/upload`: PDF upload, section segmentation, RAG indexing.
- `POST /api/v1/contracts/demo/{sample_type}`: Instant load & auto-analysis of benchmark contracts (`ma`, `cloud_dpa`, `joint_ip`, `msa`, `saas`, `nda`).
- `GET /api/v1/contracts/`: List contracts ordered by `created_at DESC`.
- `GET /api/v1/contracts/{id}`: Detailed view of contract, risks, transcript, redlines, and obligations.
- `DELETE /api/v1/contracts/{id}`: Deletes contract row, associated audit logs, and deletes ChromaDB collection.
- `POST /api/v1/analysis/{id}/trigger`: Triggers orchestrator execution.
- `GET /api/v1/analysis/{id}/redlines`: Retrieves redlines with optional `risk_severity` and `decision` filters.
- `PATCH /api/v1/analysis/{id}/redlines/{redline_id}`: Accepts or rejects a specific redline.
- `POST /api/v1/analysis/{id}/redlines/{redline_id}/regenerate`: Rewrites redline from custom prompt.
- `GET /api/v1/analysis/{id}/export/docx`: Downloads `.docx` with native Word Track Changes.
- `GET /api/v1/analysis/{id}/export/clean`: Downloads clean executable `.docx` with accepted redlines baked in.
- `GET /api/v1/analysis/{id}/export/calendar`: Downloads RFC 5545 `.ics` calendar sync file.
- `GET /api/v1/analysis/{id}/compliance/playbook`: Audits playbook adherence and deviation score.
- `POST /api/v1/analysis/deal-room/conflicts`: Runs multi-document contradiction audit across selected contracts.
- `POST /api/v1/copilot/{contract_id}/chat`: In-studio conversational legal assistant.
- `GET /api/v1/analysis/audit/summary`: Telemetry summary (tokens, cost, latency).
- `DELETE /api/v1/analysis/audit/reset`: Purges audit telemetry records.
- `GET /api/v1/analysis/llm/config` & `POST /api/v1/analysis/llm/config`: Multi-provider credentials and status.
- `GET /health`: Health check JSON (`{"status": "healthy", "version": "2.0.0"}`).
- `GET /` & `GET /studio`: Serves `backend/static/index.html`.

================================================================================
17. FRONTEND: ALPINE.JS & TAILWIND WARM EDITORIAL LEGAL STUDIO v2.1
================================================================================
Implement in `backend/static/index.html` (and sync to `frontend/public/index.html`):
- **Warm Editorial Alabaster, Terracotta & Espresso Design System**:
  - Background canvas `#F6F3EE` (`sand-100`) with pure white cards (`#FFFFFF`), soft linen inner tiles `#FAF8F5` (`sand-50`), and hairline taupe borders `#EAE4DC` (`sand-200`).
  - Primary Terracotta / Cognac accent (`brand-600: #8E5333`, hover `brand-700: #754227`, tint `brand-50: #F6EFEA`, border `brand-200: #DBC7B8`).
  - Deep Espresso Charcoal anchor (`ink-900: #1D1A18`, `ink-800: #2A2522`, muted stone `ink-500: #78716C`) for hero promo card, active segmented tabs, and active floating dock square highlights.
  - Preserved semantic diff tokens (`diff-ins` emerald `#059669`, `diff-del` crimson `#DC2626`) and provider status dots harmonized on warm linen surfaces.
- **Home & Ingestion Workspace**:
  - Top bar with drawer menu toggle, `ContractMind v2.0` branding, pill view switcher (`Ingestion Studio` | `Telemetry & Audits`), live model status indicator, and settings avatar ring.
  - Editorial display headline (`Review & negotiate contracts with multi-agent precision`) paired with reactive search input (`searchQuery` filtering analyzed contracts via `filteredContracts`) and a square Terracotta (`#8E5333`) filter toggle button (`showHomeFilters`).
  - Dark Espresso Hero Feature Card (`bg-ink-900`, `rounded-[28px]`) highlighting 4-Agent StateGraph speed with a crisp pure-white pill CTA (`Run Quick Audit`) and PDF upload jump link, plus 3 minimal workflow tiles.
  - AI Agent Models selector + Terracotta Engine Analytics donut gauge (`#tour-models`, `#tour-analytics`), PDF ingestion dropzone & Playbook cards (`#tour-ingestion`), and 6 Benchmark Deal Templates (`#tour-benchmarks`) with horizontal category pill filters (`All | M&A & IP | Cloud & SaaS | MSA & NDA` with Terracotta active state).
- **Contract Studio View**:
  - Boutique detail header with circular `<` back button, centered `"Contract Studio"` label, Deal Room shortcut, warm linen Summary Showcase (`Risk Severity X/100`, accepted count badge), and full Terracotta CTA (`Export Track Changes (.DOCX)`).
  - Espresso Pill Segmented Tabs (`bg-ink-900` active / `bg-sand-100` inactive):
    1. Redlines (with Risk & Decision filter toolbar, Accept/Reject/Reset controls, and AI Prompt Rewriter).
    2. Canvas (Synchronized Dual-Pane Review: Original Draft vs Consensus Redline Draft).
    3. Compliance (Adherence Score banner, rule checklist, remediation status).
    4. Debate (Multi-Agent StateGraph log of Auditor, Opposing Counsel, and Arbiter).
    5. Obligations (Citation, Obligor, Duty, Trigger, Breach Penalty).
- **Telemetry & Floating Frosted Bottom Dock**:
  - Telemetry view includes 4 KPI cards paired with a warm linen `Workspace Summary` receipt card (`Analyzed Contracts`, `Total Tokens`, `Active Engine`, `Total Cost`) and full-width Terracotta `Open Cross-Doc Deal Room` button.
  - Centered floating frosted bottom pill dock (`bg-white/95 backdrop-blur-xl`) highlighting the active route (`home`, `studio`, `audit`) in a Dark Espresso rounded square (`bg-ink-900 text-white`), alongside a Terracotta center upload action button, animated Guided Tour bubble (`?`), and Settings gear trigger.
- **Grounded Copilot Drawer & Deal Room Modal**:
  - Dark Espresso Copilot header (`bg-ink-900`), warm alabaster chat transcript (`bg-sand-50`), RAG citation pills, quick prompt chips, and Terracotta message bubbles (`bg-brand-600`).
  - Deal Room modal with multi-contract selection, conflict cards, precedence traps, and harmonization fixes.

================================================================================
18. DEPLOYMENT & PRODUCTION ORCHESTRATION
================================================================================
1. Local 1-Click Launch:
   - `run_contractmind.bat`: Checks Python, installs dependencies, executes `python launch.py`.
   - `launch.py`: Configures directories, runs DB migration, launches Uvicorn on `0.0.0.0:8000`, logs to `backend/backend.log`, opens default browser to `http://localhost:8000`.
2. Vercel Multi-Service Deployment (`vercel.json`):
   - Fast routing rewrites `/api/*` to FastAPI backend and `/*` to Next.js bridge serving identical v2.0 Alpine UI.

================================================================================
19. VERIFICATION CHECKLIST
================================================================================
Ensure the completed codebase satisfies all criteria:
1. [x] Zero hardcoded API keys in tracked files (use .env.example).
2. [x] PyMuPDF table parser generates valid Markdown tables.
3. [x] PII redactor removes SSNs, credit cards, bank accounts before embedding.
4. [x] ChromaDB indices are purged on contract deletion.
5. [x] Clause-level Accept / Reject decisions persist via PATCH endpoint and update UI state.
6. [x] Clause-level AI Prompt Rewriting endpoint generates custom redlines with live diff tokens.
7. [x] DOCX export reflects Accept / Reject decisions in summary table and detailed clause headings.
8. [x] Clean DOCX export bakes in accepted redlines without markup tags for execution.
9. [x] RFC 5545 iCalendar (.ics) generation exports obligation milestones directly to Google/Apple Calendar.
10. [x] In-studio Legal AI Copilot answers contract inquiries with precise clause citations.
11. [x] Deal Room multi-document conflict analyzer detects contradictions across related agreements.
12. [x] Playbook compliance engine computes quantified adherence score (0-100%) and remediation audit.
13. [x] Synchronized dual-pane canvas displays original text alongside consensus redlines.
14. [x] Redline risk-level filtering (Critical, High, Medium, Low) and decision filtering with reactive count badges.
15. [x] Real measured time.time() latency and token cost logged for all agent nodes.
16. [x] Frontend features 7-step guided tour with glowing Terracotta halo spotlight and notification bubble.
17. [x] `npm run build` on frontend completes with zero TypeScript or lint errors.
18. [x] Warm Editorial Alabaster (`#F6F3EE`), Terracotta (`#8E5333`), & Espresso (`#1D1A18`) UI synced identically between `backend/static/index.html` and `frontend/public/index.html`.
```
