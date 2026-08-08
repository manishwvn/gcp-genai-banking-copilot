# GCP_GEN_AI — Banking Document & Risk Intelligence Copilot

**Project root (local):** `/Users/manish/Desktop/GCP_GEN_AI`
**Type:** Personal learning project — GCP + GenAI, built end-to-end, implemented in Claude Code.
**Purpose:** Learn GCP (console + CLI) and GenAI/agentic AI from the ground up by building a real, deployed portfolio app. Target audience for the demo: banking-domain technical interviews.

---

## App Concept

One platform, three specialist capabilities on a shared pipeline (Cloud Storage → chunk/extract → embed → Firestore vector search → grounded generation):

1. **Filings & disclosures RAG** — SEC 10-K/10-Q filings, earnings call transcripts. Grounded Q&A with citations.
2. **KYC / bank statement extraction** — multimodal structured extraction from synthetic statements/KYC docs.
3. **Transaction fraud explainer** — small anomaly-detection model flags transactions; Gemini explains each flag, grounded against a compliance-policy corpus.

A **supervisor agent** (LangGraph, Phase 2) routes requests to the right specialist.

## Phased Roadmap

- **Phase 1 — MVP (current target):** Filings RAG chatbot only. Non-agentic. Ingest → chunk → embed (Gemini via AI Studio) → Firestore vector search → grounded chat with citations. Deployed end-to-end on Cloud Run. Must be a complete, demoable thing on its own.
- **Phase 2 — Agentic:** Add the KYC/extraction skill and fraud-explainer skill. Add LangGraph supervisor agent + a groundedness/verifier agent. Introduce evals.
- **Phase 3 — Production polish:** CI/CD pipeline, observability/monitoring, cost guardrails, interview-demo polish.

## Architecture Decisions Made

- **LLM + embeddings:** Google AI Studio Gemini API free tier (separate free pool from GCP billing) — not Vertex AI managed model endpoints, which are billed.
- **Vector store:** Firestore native KNN vector search — doubles as app DB, billed under normal Firestore read/write Always-Free quotas. No separate paid vector DB.
- **Web framework:** FastAPI. Switched from initial Flask default before Component 5 build — automatic OpenAPI/Swagger docs (better interview demo artifact), Pydantic request/response validation, async support useful for Phase 2's multi-skill supervisor routing. Decided explicitly, not defaulted.
- **Hosting:** Cloud Run (Always Free: 2M requests/month).
- **Regions:** Compute/Storage Always-Free usage restricted to `us-west1`, `us-central1`, `us-east1`.
- **Datasets:** SEC EDGAR filings + public earnings call transcript corpus (Phase 1); PaySim/Kaggle fraud datasets + synthetic KYC/statements (Phase 2).

## Hard Constraints

- **Zero spend, ever.** Always Free tier only. Set a $0/$1 budget alert as a tripwire.
- Prefer official docs (`cloud.google.com`, `docs.cloud.google.com`) over blog posts when limits are load-bearing to a decision.

## Working Conventions

- **Teaching first:** explain the "why" before implementation. Bottom-up — learn a service conceptually, navigate it in the GCP Console *and* `gcloud` CLI, do a small hands-on task, then build.
- **Session shape:** bigger chunks covering a few related services at once, not single-service micro-sessions.
- **Division of labor:** this chat = teaching, architecture decisions, planning, log-keeping. Implementation happens in **Claude Code**, in the project folder above.
- **Claude Code model usage:** use **Haiku or Sonnet 5 (low reasoning effort)** for implementation sessions to conserve tokens and avoid hitting the 5-hour session limit early. Reserve higher-effort models only if a task genuinely needs it.
- **Use subagents for noisy/verification work:** delegate detailed verification passes, log/output inspection, multi-file searches, and diagnostic checks to Claude Code subagents (isolated context, returns only a summary to the main session) rather than running verbose commands directly in the main session. Keep the main session focused on actual implementation, which is sequential and needs shared context. This conserves the main session's context/token budget, directly supporting the Haiku/Sonnet-low-effort token-conservation goal already in place.
- **Production practices from day one, no throwaway scripts:**
  - Git repo, meaningful commits from the start.
  - Python env managed via `uv` (venv + dependency locking), not ad-hoc pip installs.
  - Secrets via `.env` (local) / Secret Manager (deployed) — never hardcoded.
  - Real project structure (packages/modules), not notebook-only code.
  - README kept current; tests where reasonable.
- **Session-end log:** every session in this chat ends with a short dated entry (3–6 lines: what was learned/decided, what got built, next step) appended to this file, so it can be carried into Claude Code.
- **New-session flags:** when a chunk of work is complete enough that the next component should start a **fresh Claude Code session** (to avoid context bloat and conserve the session window), the session-end log entry will explicitly say so — e.g. "Start new Claude Code session for: Firestore vector search setup."
- **`learnings.md`** (maintained alongside this file, same directory): one section per service/concept — what it is, why it's used here, implementation snippets, and an ELI5 explanation with examples. Update this file after every session in which something new is learned or implemented. Quick reference for yourself and for Claude Code sessions.

## Session Log

### 2026-08-05 — Project kickoff & GCP fundamentals
- Landscape review: GCP Always Free tier services (compute, storage, DB, AI APIs, ops) confirmed current as of Aug 2026.
- Confirmed Firestore native vector search fits inside Always-Free Firestore quotas — key unlock for a $0 RAG architecture.
- Brainstormed and merged three banking-flavored app ideas into one phased platform (filings RAG → KYC extraction → fraud explainer, unified by a supervisor agent).
- Decided Phase 1 MVP = filings/earnings-call RAG chatbot only.
- **Executed:** Verified `gcloud` CLI installed (v578), authenticated (manishwvn998@gmail.com), created new GCP project `gcp-genai-banking`, linked billing account (0147EC-94B896-30A818).
- Created `learnings.md` with foundational service documentation (GCP fundamentals, IAM, Cloud Storage, Firestore, Gemini API, Cloud Run, LangChain/LangGraph, production practices) — to be expanded as we progress.
- Next step: IAM deep-dive (service accounts, roles, keys) — hands-on in Console/CLI, then start Phase 1 implementation sprint in Claude Code.

### 2026-08-05 — IAM setup, git init
- **Executed:** IAM deep-dive hands-on. Created service account `filings-rag-app`. Assigned roles: `roles/datastore.user` (Firestore) + `roles/storage.objectViewer` (Cloud Storage). Created private key, saved locally.
- **Gotcha hit:** `roles/firestore.user` and `roles/firestore.editor` not valid at project level — used `roles/datastore.user` instead (Firestore runs on Datastore API under the hood, IAM roles inherited from there). Logged in `learnings.md`.
- **Executed:** Initialized git repo. Created `.gitignore` (protects service account key files, `.env`). Created `.env` with placeholder credentials. First git commit made.
- Next step: Set up `uv` venv + core Python project structure. Start new Claude Code session for Phase 1 implementation.

### 2026-08-05 — Python project setup, auth skeleton, verification
- **Executed:** IAM setup completed — service account `filings-rag-app` created, roles assigned (`datastore.user`, `storage.objectViewer`), private key created.
- **Executed:** Git initialized, `.gitignore` + `.env` created.
- **Executed:** Python project structure via `uv` — venv, `pyproject.toml`, `src/copilot/`, `tests/`.
- **Executed:** Auth skeleton implemented — `auth.py` (loads credentials), `firestore_client.py` (`get_db()` helper), `embeddings.py` (stub).
- **Validated:** All 8 setup checks passed — file structure, deps, imports, code, git, README, `.gitignore`.
- **Executed:** Ran `main.py` — Firestore client initialized successfully, auth end-to-end verified.
- **Flag:** `google-generativeai` package deprecated upstream — swap to `google-genai` before Phase 2 heavy use. Noted in `learnings.md`.
- Next step: Start new Claude Code session for Phase 1 implementation (document ingestion → chunking → embedding → Firestore vector storage → retrieval → Cloud Run deployment).

### 2026-08-05 — Component 1: Document Ingestion & Chunking (complete)
- **Built:** Document ingestion component with synthetic test fixtures (sample 10-K PDF, earnings call transcript); `document_ingestion.py` implemented with `read_pdf_text()` (PDF → text via pdfplumber), `chunk_text()` (sentence-boundary chunking with overlap), `create_firestore_chunks()` (write to Firestore).
- **Infrastructure gap resolved:** Firestore API not auto-enabled on new project, and no native-mode database instance created. Both are one-time provisioning steps required before any client writes succeed. Enabled API (`gcloud services enable firestore.googleapis.com`), created native-mode database (us-central1, freeTier: true). Gotcha #5 added to `learnings.md`.
- **End-to-end verified:** Sample 10-K chunked and written to Firestore collection `filings_chunks` (documents visible in GCP Console, live read confirmed).
- **Detailed verification pass caught 3 gaps, all fixed:** (1) No test coverage for `chunk_text()` — added `tests/test_document_ingestion.py` with sentence-boundary, overlap, single-chunk edge cases (4/4 tests passing). (2) Unused `nltk` dependency (chunking uses regex) — removed `nltk` + transitive deps (`joblib`, `regex`), relocked with `uv sync`. (3) Firestore provisioning gotcha undocumented — logged in `learnings.md` gotcha #5.
- **Data integrity:** Sequential chunk indices, no duplicates, no chunks near 1MB Firestore document limit, no empty/garbage text.
- **Committed:** Build + verification fixes.
- **Status:** Component 1 COMPLETE and verified.
- Next step: Start new Claude Code session for Component 2 — Embedding generation (Gemini API embeddings → Firestore vector fields).

### 2026-08-05 — Post-commit hook for component-done workflow
- **Executed:** Set up `.githooks/post-commit` hook. Prints banner when commit message contains `[component-done]` marker, reminding to run the doc-update prompt in doc-updates session. Configured via `git config core.hooksPath .githooks`. Tested working (fires on marker, silent otherwise).
- **Committed:** 048d717.
- **Going forward:** Mark the final commit of each verified component/phase with `[component-done]` to auto-trigger doc reminder.

### 2026-08-05 — Gemini API free-tier key detour & Component 2: Embedding Generation (complete)

**a) Gemini API free-tier key detour:**
- Discovered creating a Gemini API key under gcp-genai-banking (billing-linked project) automatically promotes the key to paid Tier 1/Postpay — confirmed via Google's billing docs: tier is determined by project's billing account status, not usage or key settings.
- "Buy credits" purchase dialog appeared when viewing that key's billing setup — caught before any charge occurred.
- Fix: created second GCP project `gcp-genai-llm-free` with NO billing account linked, created Gemini API key there instead — confirmed "Free tier" badge in AI Studio. Kept gcp-genai-banking as default project, updated .env with real free-tier key.
- **Architectural note:** GCP Always-Free and AI Studio Gemini free tier are separate quotas requiring separate projects (billing-linked vs. billing-absent).

**b) Component 2 (Embedding Generation) — built and verified:**
- Migrated `google-generativeai` (deprecated) to `google-genai` (new client is object-oriented: `genai.Client(api_key=...)` + method calls vs. old module-level config+free-functions).
- Discovered via live `ListModels` that `text-embedding-004/005` no longer served; used `gemini-embedding-001` with `output_dimensionality=768`.
- Implemented `embed_text()` (retry + exponential backoff) and `embed_filings.py` (idempotent, skips pre-embedded chunks).
- Created Firestore composite vector index on `filings_chunks.embedding` (768-dim), confirmed state READY via gcloud.
- Verification pass (not logs-only): live Firestore confirmed 768-dim vectors on chunks, idempotency rerun (0 embedded/2 skipped), index status check, pytest (8/8 passing).
- Found gotcha: `firestore.Vector` not at package root in installed `google-cloud-firestore`; must import from `google.cloud.firestore_v1.vector`.
- API quota used: 2 embedding calls (nowhere near free-tier limits).
- **Committed:** [component-done].
- **Status:** Component 2 COMPLETE and verified.
- **Next step:** Component 3 (vector index) already done this session — next: Component 4 (Retrieval & RAG chain: query embedding → Firestore `find_nearest` → prompt format → Gemini generation with citations).

### 2026-08-05 — Phase 1 Component 4: Retrieval & Grounded RAG Chain (complete)

**a) Retrieval & RAG Chain — built:**
- Implemented `src/copilot/retrieval.py`: `retrieve_relevant_chunks()` (query text → embed via Gemini API → Firestore `find_nearest(embedding, 768-dim vectors, distance_type=COSINE, limit=top_k)` → sorted results by relevance).
- Implemented `src/copilot/rag_chain.py`: `generate_grounded_answer()` (takes query + retrieved chunks, strict grounding prompt, generates answer with citations programmatically attached from chunk metadata, explicit refusal instruction for out-of-scope questions).
- Implemented `rag_query()` end-to-end chain orchestrator (query → retrieve → generate).
- Implemented `src/copilot/query_filings.py` CLI entry point for interactive queries.
- **Design decision — strict grounding:** Citations are attached from retrieved chunk metadata and document source in code, not trusted from model's generated text. Model cannot fabricate sources. Out-of-scope queries explicitly instructed to refuse rather than hallucinate.

**b) Answer grounding field:**
- Added boolean `answer_grounded` to distinguish two scenarios: (1) answered from context (`answer_grounded=True`, citations present), vs. (2) searched but found no usable context (`answer_grounded=False`, no citations but refusal still grounded). Both have citation lists non-empty or empty by design intent — the boolean disambiguates the user-facing meaning.

**c) Model selection verification — live testing required:**
- `gemini-2.5-flash`: failed live with 404 response — account-level access restriction, model sunset for new accounts (unrelated to billing tier).
- `gemini-2.0-flash-001`: failed live with 429 response — free-tier quota explicitly zero for this model (distinct from Component 2's "model not listed" gotcha — this is "model exists but isn't accessible for this account/tier").
- `gemini-flash-latest`: succeeded — nonzero free-tier quota, no access restriction. Used going forward. Both failure modes documented in `learnings.md` with raw error bodies, explicitly separated from embedding-model gotchas.

**d) End-to-end verification:**
- Grounded query ("What are ACME's main financial risks as disclosed in their 10-K?") returned accurate answer with citations matching live filing content.
- Refusal query ("What is the population of Tokyo?") correctly refused out-of-scope (answer_grounded=False, no citations).
- Both paths validated live against real Firestore data and Gemini API.

**e) Testing & test-isolation fix:**
- Test suite: 15/15 passing, mocked (no real API/quota used).
- Coverage: retrieval ranking, grounding prompt formatting, citation attachment, refusal path, edge cases (empty results, malformed chunks).
- Fixed test-isolation bug: mocked Gemini client leaked between tests due to missing reset fixture — added per-test client mock setup.
- **Committed:** [component-done].

**f) Deferred to Phase 2:**
- Formal grounding/hallucination evaluation metrics (e.g. precision@k, recall@k, faithfulness scoring) — specific approach/tooling not yet decided, research when Phase 2 eval work begins.
- LangGraph supervisor routing (stub only in Phase 1).
- Real fraud-explainer and KYC-extraction skills.

- **Status:** Component 4 COMPLETE and verified.
- **Phase 1 MVP readiness:** Core retrieval + grounded RAG chain done. Next: deploy to Cloud Run, add HTTP API layer (FastAPI), integrate synthetic dataset (SEC filings corpus).

### 2026-08-07 — Pre-Component 5 conceptual refresher & infrastructure setup

**a) Conceptual deep-dive:** Covered foundational concepts needed before Component 5 build:
- **APIs & HTTP fundamentals:** methods (GET/POST), endpoints, request/response bodies, status codes — needed to expose `rag_query()` beyond local Python.
- **FastAPI framework:** HTTP routing, Pydantic request/response validation, auto-generated OpenAPI docs (`/docs`). Chosen over Flask (explicit decision made earlier, documented in Architecture Decisions).
- **Containers & Docker:** Dockerfile anatomy (FROM/COPY/RUN/CMD), image vs. container (class vs. object). Why: "works on my machine" problem — Cloud Run's servers don't have your laptop's dependencies.
- **Cloud Run:** serverless container hosting, scales to zero (no idle cost), Always-Free: 2M requests/month. Attached service account identity (no key file in container) vs. local key-file auth.
- **Secret Manager:** credential storage, versioned and access-controlled. Learned: once a secret appears in any conversation/history, treat as compromised — rotate at source, add new version, destroy (not disable) the old version.
- **Cloud Run service account identity model:** same service account (`filings-rag-app`) works for both local (key file) and Cloud Run (attached identity) contexts. Code uses `google.auth.default()` which checks environment first (Cloud Run) then falls back to local key file.

**b) Security incident & response (real, this session):**
- During manual secret creation, gemini-api-key value was pasted into an AI chat conversation as part of a command example, despite intent to keep secrets out of AI context by running commands manually.
- **Lesson:** once a credential appears in any conversation history (including AI), treat it as compromised regardless of whether execution was manual/local.
- **Mitigation:** rotated key in AI Studio, added new value as secret version 2 via `gcloud secrets versions add`, destroyed (not disabled) version 1 via `gcloud secrets versions destroy 1 --secret=gemini-api-key` — destroy is irreversible and actually deletes the value data, vs. disable which only deactivates but keeps it recoverable.
- **Future practice:** when showing a command that embeds a secret value, redact the value in anything shown to another party (including AI), even if underlying execution is manual.

**c) Infrastructure for Component 5 prepared:**
- Secret Manager API enabled, `gemini-api-key` secret created (version 1, then rotated to version 2).
- Firestore, Cloud Storage, Cloud Run, Cloud Build APIs already enabled (from Components 1–4).
- `filings-rag-app` service account confirmed sufficient for Cloud Run deployment: already has `roles/datastore.user` (Firestore), `roles/storage.objectViewer` (Cloud Storage), and `roles/secretmanager.secretAccessor` (Secret Manager). No new service account needed.

**d) Next step:** Component 5 build (FastAPI HTTP API, Dockerfile, Cloud Run deployment) not yet started, pending this doc update.

- **Status:** Pre-build conceptual work complete. Infrastructure ready for Component 5.

### 2026-08-07 — Phase 1 Component 5: FastAPI Service, Docker, Cloud Run Deployment (complete)

**a) Component 5 built — FastAPI HTTP API layer:**
- Implemented `src/copilot/api.py`: POST `/query` (Pydantic request/response validation, structured error handling), GET `/health`, JSON error responses with status codes.
- Implemented `app.py` (uvicorn entry point).
- Created Dockerfile (`python:3.11-slim` base, `COPY --from` uv binary, two-layer `uv sync` for dependency caching, non-root `appuser`, direct `.venv/bin/uvicorn` in CMD).
- Created `.dockerignore` (excludes git, tests, caches, local keys — smaller image, faster build).
- **Design decision — strict grounding at HTTP boundary:** API response includes `answer_grounded` boolean; client code can distinguish answered-from-context vs. refused-out-of-scope without parsing model text.

**b) Infrastructure & deployment model:**
- **Service account reuse:** `filings-rag-app` already has all needed roles (Firestore, Storage, Secret Manager). No new identity created. Cloud Run attaches this SA as the pod identity; code uses `google.auth.default()` which detects Cloud Run environment and auto-authenticates — no key file in container.
- **Secret injection:** `GEMINI_API_KEY` stored in Secret Manager; deployed with `--set-secrets=GEMINI_API_KEY=gemini-api-key:latest` (Cloud Run auto-loads at container startup). Verified secret permission check on startup.
- **Public deployment:** `--allow-unauthenticated` used for demo accessibility. Explicit decision — synthetic data only, safe for portfolio demo. Noted in commit message.

**c) Cost & abuse safeguards:**
- Cloud Run `--max-instances=3` cap to prevent runaway scaling from quota abuse or DoS.
- **$0/$1 budget alert finally configured** on billing account (0147EC-94B896-30A818) after being deferred since project setup — this closes a gap identified in kickoff but never implemented until now. Discovered pre-existing $5 budget alert already on account (thresholds 0.5/0.9/1.0/1.5).
- All quotas verified as Always-Free: Firestore, Cloud Storage, Cloud Run, Secret Manager, Gemini Embeddings API, Gemini generation API.

**d) Gotchas hit & fixed:**
1. **Cloud Build IAM propagation lag:** First deploy failed with `cloudbuild.builds.builder` missing on Compute Engine default service account. Granted role via `gcloud iam service-accounts add-iam-policy-binding`; confirmed this rides on pre-existing `roles/editor` grant (broad, not introduced by this session). Gotcha documented in learnings.md.
2. **Non-root Docker user + `uv run` at container CMD time:** Initial attempt ran service as non-root user with `CMD ["sh", "-c", "uv run uvicorn ..."]`. This broke at startup: `uv run` re-resolves/downloads dependencies on every container start (not build time), hitting permission friction when appuser couldn't write to uv's cache, plus wasting startup time. Fixed by invoking prebuilt venv binary directly in CMD: `CMD ["sh", "-c", ".venv/bin/uvicorn app:app ..."]` — dependency resolution happens once at image build time, no re-resolution at runtime. General lesson: `uv run` is fine for local dev, but in container CMD prefer calling the venv's binaries directly for faster, more reliable startup.

**e) Verification — live end-to-end against deployed URL:**
- GET `/health` → 200 OK.
- POST `/query` with grounded question → 200, `answer_grounded=true`, real citations from live Firestore.
- POST `/query` with out-of-scope question → 200, `answer_grounded=false`, refusal (no hallucination).
- OpenAPI docs at `/docs` working and accurate.
- All requests logged; response times <2s (cold start + embedding + retrieval + generation).
- Deployed service URL: `https://filings-rag-api-27353588174.us-central1.run.app`

**f) Testing & verification approach:**
- Test suite: 18/18 passing (2 benign third-party deprecation warnings, not actionable).
- Adopted subagent delegation for verification passes (curl output, logs, status checks) — kept verbose output out of main session context per new CLAUDE.md convention.
- Coverage: Pydantic validation (invalid payloads rejected), health check, RAG pipeline integration, error cases, deployment readiness.

**g) Commits:**
- c69c756 — `[component-done]` — built and verified Component 5.

**h) Phase 1 complete:**
All five components built, tested, verified, and deployed:
1. Document Ingestion & Chunking (Component 1) — PDF → Firestore chunks
2. Embedding Generation & Vector Indexing (Components 2 & 3) — Gemini embeddings → Firestore vectors
3. Retrieval & Grounded RAG Chain (Component 4) — query → retrieval → generation with citations
4. FastAPI HTTP API Layer (Component 5) — `POST /query`, `GET /health`, deployed on Cloud Run
5. Zero spend maintained throughout — all services on Always-Free tier, now backed by budget alerts.

**Status:** Phase 1 MVP COMPLETE and deployed.

**Next phase:** Phase 2 — agentic layer. Add KYC/statement extraction skill and fraud-explainer skill. Introduce LangGraph supervisor agent to route between three specialist capabilities. Add groundedness/verifier agent. Introduce formal evaluation metrics. Recommend fresh planning conversation given multi-agent architecture scope shift from Phase 1's single-pipeline MVP.

### 2026-08-08 — GitHub Publish, Licensing, Documentation Polish & Accuracy Audit

**a) GitHub repository created and published:**
- Executed: `gh repo create gcp-genai-banking-copilot --public --source=. --remote=origin --push` (created public GitHub repo, pushed Phase 1 complete code, set remote upstream).
- Security pre-flight: verified no hardcoded secrets or keys in git history — the Gemini API key that was chat-leaked during pre-Component-5 session was rotated immediately (never committed), so no compromise in repo.
- Added GitHub topics: `gcp`, `genai`, `gemini-api`, `rag`, `firestore`, `cloud-run`, `banking`, `portfolio`.

**b) License and branding:**
- Added MIT License file (`LICENSE`). Confirmed auto-detection by GitHub (shows MIT badge on repo).
- Updated repo description: "Banking Document & Risk Intelligence Copilot — Filings RAG MVP on GCP Always-Free."

**c) README rewritten (portfolio-quality):**
- Replaced stale Component-1-era README with comprehensive documentation:
  - Project overview (problem statement, use cases, Phase 1 MVP scope).
  - Live demo link: `https://filings-rag-api-27353588174.us-central1.run.app`.
  - Architecture diagram (markdown mermaid: data flow Cloud Storage → chunk → embed → Firestore → retrieval → generation).
  - Tech stack section (FastAPI, Firestore, Gemini API, Cloud Run, docker, uv).
  - API usage example (curl POST `/query` with real-world question, real response).
  - Setup instructions (clone, uv sync, .env, local run, Cloud Run deploy).
  - Future work (Phase 2 agentic layer).

**d) Documentation consistency audit (CLAUDE.md & learnings.md):**
- Executed full consistency audit as a subagent — found 5 stale-content issues:
  1. Firestore.Vector import example (line ~305) showed wrong top-level import — corrected to show `from google.cloud.firestore_v1.vector import Vector`.
  2. Embedding model example (line ~388) showed deprecated `text-embedding-005` — corrected to `gemini-embedding-001` with `output_dimensionality=768`.
  3. Rate-limits section (lines ~354, 356) listed models as available that were later found inaccessible (`gemini-2.5-flash` 404, `text-embedding-005` sunset) — updated to reflect live-tested reality: `gemini-flash-latest` (working), with cross-references to Component 4's gotchas.
  4. "To Be Added" placeholder (lines ~1319-1327) listed "LangChain & LangGraph Patterns" as pending, but section exists at lines 523–589 — removed from placeholder, kept legitimately-still-pending Phase 2 items.
  5. Last-updated timestamp (line 1331) showed "Pre-Component 5" but Component 5 content was present — updated to "2026-08-08 — through Phase 1 completion."
- Added new bridge section: "Phase 1 Component Build Log" (41 lines) at the top of learnings.md after the intro — concise chronological summary of what each component (1-5) built, which files/tech, relevant concept-section pointers, and status. Bridges CLAUDE.md session log to learnings.md concept reference structure.

**e) Second-pass accuracy fix (this session):**
- During the component build log creation, caught that the new Component 5 entry claimed "Alpine base, multi-stage" — verified against the real Dockerfile and corrected to `python:3.11-slim` base, `COPY --from` uv binary.
- Second review of learnings.md "Component 5: Real Build Notes" section found the Dockerfile snippet itself was stale:
  - Line 1319 showed `CMD ["sh", "-c", "uv run uvicorn ..."]` but should be `.venv/bin/uvicorn` (the actual fix documented in the gotcha paragraph directly below contradicted the snippet).
  - Missing `USER appuser` line (added after initial root-only build).
  - Corrected snippet and supporting prose to match the deployed file.
- Cross-checked against CLAUDE.md and found matching errors that were never fixed after the initial session:
  - Line 184: still claimed "Alpine base" — corrected to `python:3.11-slim`, COPY --from, two-layer uv sync, non-root appuser, direct venv binary.
  - Line 190: used old flag `--set-env-vars=GEMINI_API_KEY=sm://gemini-api-key` — corrected to `--set-secrets=GEMINI_API_KEY=gemini-api-key:latest` (verified against learnings.md's own "Real Working Deploy Command").
  - Lines 198–201: claimed 3 gotchas, but gotcha #3 ("Venv binary path resolution: `/venv/bin/python -m uvicorn...`") was fabricated/misremembered — the real fix was described in gotcha #2 (use `.venv/bin/uvicorn` directly, not `uv run`). Merged gotcha #3 into gotcha #2 with full detail; now 2 real gotchas only.

**f) Commits:**
- a2ff72a — `docs: add MIT license`
- f84d559 — `docs: rewrite README as portfolio-quality project overview`
- Both consistency audit fixes (5 stale items corrected, Component Build Log added, second-pass accuracy corrections) staged for this commit.

**Status:** Phase 1 fully complete, documented, tested, deployed, licensed, published, and now doc-audited twice for accuracy. Ready for portfolio demo.

**Next:** Phase 2 planning conversation (agentic layer, multi-skill supervisor, formal evaluation).
