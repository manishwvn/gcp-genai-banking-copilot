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
