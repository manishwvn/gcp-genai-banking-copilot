# learnings.md — GCP_GEN_AI Service & Concept Deep-Dives

This document captures what was learned about each GCP service and concept used in the Banking Copilot project, with implementation snippets, ELI5 explanations, and gotchas. Updated after each phase/session.

---

## Phase 1 Component Build Log — Bridge to Concept Sections

Quick reference: what each component built and which concept sections explain the underlying tech. Full session-log entries and deployment details in CLAUDE.md.

### Component 1: Document Ingestion & Chunking
- **Built:** `src/copilot/document_ingestion.py` — PDF text extraction (pdfplumber), sentence-boundary chunking with overlap, Firestore writes to `filings_chunks` collection.
- **Key concepts:** "Document Ingestion & Chunking Strategy" (this file).
- **Status:** Complete, live Firestore data verified.

### Component 2: Embedding Generation & Vector Indexing
- **Built:** `src/copilot/embeddings.py` (retry logic), `embed_filings.py` (idempotent embedding script), `google-genai` SDK migration (from deprecated `google-generativeai`).
- **Tech:** Gemini API embeddings, `gemini-embedding-001` (768-dim), migrated to `google-genai` client.
- **Key concepts:** "Embedding Generation & Vector Indexing" (this file, includes model-availability gotchas); "Deprecation & Migration Notes".
- **Status:** Complete, 768-dim vectors in Firestore, Firestore composite vector index created.

### Component 3: Vector Index Setup
- **Built:** Firestore composite index on `filings_chunks.embedding` (768-dim, COSINE distance).
- **Key concepts:** "Embedding Generation & Vector Indexing" section (index creation commands).
- **Status:** Complete, index state READY.

### Component 4: Retrieval & Grounded RAG Chain
- **Built:** `src/copilot/retrieval.py` (Firestore `find_nearest` + embedding), `src/copilot/rag_chain.py` (grounded generation with programmatic citations), `src/copilot/query_filings.py` (CLI query tool).
- **Tech:** Firestore vector search, Gemini API generation (`gemini-flash-latest`, NOT `gemini-2.5-flash`), strict grounding prompt + programmatic citations, `answer_grounded` boolean for ambiguity resolution.
- **Key concepts:** "Retrieval & Grounded Generation (RAG Chain)" section (design rationale, model-access gotchas with full error bodies); "Web APIs & HTTP Fundamentals" (foundation for Component 5).
- **Status:** Complete, live end-to-end verified against real Firestore data.

### Component 5: FastAPI HTTP API + Docker + Cloud Run Deployment
- **Built:** `src/copilot/api.py` (FastAPI app with POST `/query`, GET `/health`, Pydantic validation), `app.py` (uvicorn entry point), Dockerfile (multi-stage, `uv` for dependency management), `.dockerignore`, Cloud Run deployment via `gcloud run deploy --source=.`.
- **Tech:** FastAPI framework (auto OpenAPI docs at `/docs`), Docker containerization (Alpine base, two-stage builds for layer caching), Cloud Run serverless hosting (Always-Free tier), service account attached identity (no key files in container), Secret Manager credential injection for `GEMINI_API_KEY`.
- **Key concepts:** "FastAPI Framework", "Containers & Docker", "Cloud Run", "Secret Manager", "Cloud Run Service Account Identity", "Component 5: FastAPI + Docker + Cloud Run — Real Build Notes" (full deployment details and live verification results).
- **Live URL:** `https://filings-rag-api-27353588174.us-central1.run.app` (public, `--allow-unauthenticated`).
- **Status:** Complete, deployed, live end-to-end verified (health check, grounded query, refusal query, OpenAPI docs all working).

## Phase 1 End-to-End Pipeline Walkthrough

> Example data in this walkthrough was captured live against the deployed service on 2026-08-08 — see raw JSON responses in git commit history for unmodified output.

This section tells the story of what happens to a document and a question, start to finish—how PDF becomes answer with citations. The concept sections below explain each underlying technology in depth; this walkthrough shows how they connect and why each step exists.

### The Starting Point

Before anything: a PDF file sits in a folder, ignored. After Component 5 ships: a live URL answers questions about that PDF with real citations, no hallucination, no guessing.

The journey: PDF → chunks → embeddings → vector index → retrieval pipeline → grounded generation → HTTP API → deployed.

### Components 1–3: Turning a PDF into a Searchable Pile of Meaning

**Ingestion & chunking (Component 1):**
Raw PDF text is too broad. If you embed a whole 50-page 10-K filing as one vector, the vector captures only high-level gist—questions about specific financial metrics get lost. Solution: break text into ~800-token chunks (~3200 characters) at sentence boundaries, with 100-token overlap between adjacent chunks. Why overlap? A fact often spans chunk edges. Without overlap, retrieval misses context that lives in the seam. With it, no answer is ever "incomplete due to boundary."

`chunk_text()` in `document_ingestion.py` handles this: feeds sentences into a buffer, spills to a chunk when size exceeds 800 tokens, seeds the next chunk's buffer with the last 100 tokens from the one that just spilled. Result: a collection of overlapping passages, each grounded in the original text, each self-contained enough to be understood alone.

**Embedding (Component 2):**
Each chunk gets embedded into a 768-dimensional vector using Gemini's `gemini-embedding-001` model. A vector is just 768 numbers. What do they represent? Semantic meaning. Two chunks about "debt obligations" will have similar vectors; two about "debt" and "weather" will not. The vector isn't keywords or words at all—it's a high-dimensional fingerprint of meaning that the model learned.

`embed_text()` calls `client.models.embed_content()` with `output_dimensionality=768`. One call per chunk. Why Gemini's embedding, not a separate open-source model? It's free-tier accessible, needs no management, and stays in the same semantic space as the generation model we'll use later (Component 4). Consistency matters: if the embedding model and generation model "speak different languages," retrieval and generation get misaligned.

**Indexing (Component 3):**
Firestore can search millions of vectors instantly using a native KNN index—but only after you build it explicitly. Create a composite index on the `embedding` field (768 dimensions, cosine distance). This isn't a data-processing step (no code to write), but it's essential infrastructure. Without it, `find_nearest` fails silently. Think of it like a card catalog in a library: without the index, the librarian has to read every card to find your request. With it, lookup is O(log n).

### Component 4: The Actual Brain—Retrieval + Grounded Generation

Walk through a real example end to end. The question: "What are ACME's main financial risks mentioned in the filing?"

**Step 1: Embed the question.**
`retrieve_relevant_chunks()` takes the question and runs it through `embed_text()`—the same embedding model as the chunks. This produces a 768-dimensional query vector in the same semantic space. The question and the chunks now speak the same language.

**Step 2: Find nearest neighbors.**
`find_nearest()` (Firestore's native KNN search) compares the query vector against all 768-dim chunk vectors using cosine distance. It returns the top results ranked by relevance. Cosine distance: a number between 0 and 1, where 0 = identical meaning, 1 = orthogonal/opposite. Lower distance = higher relevance.

Live example on the ACME financial risks question: retrieval returned 2 chunks (all chunks currently in the sample dataset — top_k=4 was configured, but only 2 chunks exist in Firestore from the single ingested sample filing):
- chunk_index=0, distance=0.2366 (high relevance)
- chunk_index=1, distance=0.3828 (good relevance)

These chunks contain Item 1A risk factor disclosures from the sample 10-K filing. The distances are low enough that retrieval found useful context to feed to generation.

**Step 3: Build a grounding prompt.**
`_build_prompt()` constructs the precise prompt sent to Gemini. Core text: "Answer ONLY using the provided context. If the answer is not present in the context, respond exactly: 'I don't have enough information in the available documents to answer this.' Do not use outside knowledge."

Then it lists the retrieved chunks as numbered context blocks: "[1] first chunk text. [2] second chunk text..." Then the question. This design forces the model into a choice: answer from what's in the context and cite which blocks [1], [2], etc., or refuse. No middle ground where it hallucinates.

**Step 4: Generate with the model.**
`generate_grounded_answer()` calls `client.models.generate_content()` with the prompt. The model reads the context and question, generates an answer. Real example (ACME financial risks question): the model generated:

"According to the provided context, ACME's main risk factors mentioned under Item 1A in the filing are: Credit Risk (borrower default risk on loan portfolio, particularly in commercial real estate) [1]; Interest Rate Risk (Federal Reserve rate changes affecting net interest margin and securities value) [1]; Cybersecurity Risk (cyberattacks, data breaches, system failures) [1]; Regulatory Risk (Basel III capital requirement changes) [1]; Liquidity Risk (dependence on deposits and wholesale funding, risk of sudden withdrawal) [1], [2]."

The model references context blocks [1] and [2] where it found each risk cited. Grounded, specific, no invented risks.

**Step 5: Attach citations programmatically.**
Here's the key design difference: citations are NOT extracted from the model's generated text. Instead, they're constructed in code from the retrieval-step metadata. Each of the retrieved chunks becomes one citation: `{source, chunk_index, distance}`. The model's references ([1], [2]) are a hint for humans; the authoritative citations come from what was actually fed into the prompt.

Why this design? The model cannot fabricate sources. It cannot claim it cited a source that wasn't in the retrieval results. Citations are grounded by construction.

**Step 6: The answer_grounded flag.**
After generation, code checks: did the model refuse (return the exact refusal text) or answer? If it answered, `answer_grounded=True`. If it refused, `answer_grounded=False`. Both paths can have a citations list (non-empty if chunks were retrieved, empty if retrieval found nothing). This boolean disambiguates two scenarios: (1) answered from context (citation list says which chunks), vs. (2) searched but found no usable context (citation list is empty, answer is the refusal text).

Example refusal (ACME filing, question "What is the population of Tokyo?"): Retrieval returns chunks from the 10-K with COSINE distances 0.5502 (chunk_index=1) and 0.5505 (chunk_index=0)—very weak matches (high distance numbers). The model reads these financial-risk chunks and sees no path to answering about Tokyo's population. It returns the refusal text exactly: "I don't have enough information in the available documents to answer this." Result: `answer_grounded=False`, `citations=[{chunk_index=1, distance=0.5502}, {chunk_index=0, distance=0.5505}]`, answer is the refusal. The API caller knows: not a hallucination, just out of scope. The high-distance citations prove retrieval tried but found nothing useful.

### Component 5: Making It Reachable

Components 1–4 live in Python. Component 5 wraps them in HTTP. POST `/query` endpoint takes a JSON request `{question: "..."}`, validates it with Pydantic, calls `rag_query()` (the end-to-end orchestrator), and returns `{answer, citations, answer_grounded}` as JSON.

Infrastructure for Component 5: see learnings.md "Component 5: FastAPI + Docker + Cloud Run — Real Build Notes" section for full deployment details. Summary: Dockerfile packages the Python app, `gcloud run deploy` pushes it to Cloud Run. Service account identity (no key files in container) authenticates to Firestore and Secret Manager at runtime. Live at `https://filings-rag-api-27353588174.us-central1.run.app`.

### The Full Line, One More Time

PDF comes in → extracted to text → chunked with overlap → each chunk embedded to a 768-dim vector → vectors indexed in Firestore → question arrives at HTTP endpoint → question embedded with same model → Firestore finds nearest chunks (distances 0.24–0.38 for good matches, 0.55+ for weak ones) → chunks + question fed to Gemini with strict "answer only from context" prompt → Gemini generates answer or refuses → citations attached from retrieval metadata with distances, not from model text → response sent back as JSON with `answer_grounded` flag. Complete pipeline, zero hallucination by design, every citation grounded in actual retrieved text and ranked by distance.

---

## GCP Fundamentals — Projects, Billing, and `gcloud` CLI

### What It Is
Google Cloud is organized into **projects** — isolated workspaces where you create resources (VMs, databases, APIs). Every resource belongs to exactly one project. A **billing account** attaches to one or more projects and tracks your usage/costs. The **`gcloud` CLI** is Google's command-line tool for managing GCP resources without using the web Console.

### Why It's Used Here
We need a dedicated project to organize all resources for this app (Cloud Storage, Firestore, Cloud Run, etc.) and attach billing (required to access Always-Free tiers, even if you're not charged). Using `gcloud` CLI from day one trains the muscle memory of real GCP workflows — everything reproducible, automatable, and version-controllable.

### Key Concepts

**Project ID vs. Project Name:**
- **Project ID** (e.g., `gcp-genai-banking`) — immutable, unique across Google Cloud, used in all CLI/API commands and URLs. Must be lowercase, alphanumeric + hyphens, 6–30 chars.
- **Project Name** (e.g., `GCP GenAI Banking Copilot`) — human-readable, shown in Console UI, can have spaces and uppercase. Not used in commands; just for your own reference.

**Billing Account:**
- Links to projects to enable billing-dependent services (including Always-Free tiers).
- Even if you never pay, the account must be active and in good standing.
- One billing account can be linked to multiple projects.

**`gcloud` Config:**
- `gcloud config` manages your local CLI settings — which project is "active," which account is logged in, which region/zone you prefer, etc.
- Active project is the default used by most `gcloud` commands unless you override with `--project=<PROJECT_ID>`.
- Settings live in `~/.config/gcloud/configurations/config` (don't edit directly; use `gcloud config` commands).

### Implementation Snippets

**Check if `gcloud` is installed:**
```bash
gcloud --version
```

**Authenticate (first time):**
```bash
gcloud auth login
```
Opens a browser for Google account sign-in, then stores credentials locally.

**List billing accounts:**
```bash
gcloud billing accounts list
```

**Create a project:**
```bash
gcloud projects create gcp-genai-banking --name="GCP GenAI Banking Copilot" --set-as-default
```

**Link billing to a project:**
```bash
gcloud billing projects link gcp-genai-banking --billing-account=0147EC-94B896-30A818
```

**Check current active project:**
```bash
gcloud config get-value project
```

**Set a different project as active:**
```bash
gcloud config set project gcp-genai-banking
```

### ELI5 Explanation

Think of GCP like **renting a building.**
- A **project** is a floor in the building. Everything you build on that floor (desks, storage, etc.) belongs there.
- A **billing account** is your lease/contract. You need one to rent any floor at all.
- The **`gcloud` CLI** is like having a checklist and a walkie-talkie instead of walking to each desk in person. You say "add a desk in the east corner," it gets done, you see it in the Console later if you want to verify.

In practice:
- One billing account can rent multiple floors (projects) — useful if you have different apps or environments.
- Each project is isolated; you can delete one without touching others.
- The CLI is faster and scriptable; the Console is better for seeing the big picture and learning visually.

### Common Gotchas

1. **Project ID must be lowercase.** Trying `GCP-GEN-AI` fails; must be `gcp-genai-banking`.
2. **Project ID is immutable once set.** You cannot rename it. Choose carefully.
3. **Billing account must be active to use Always-Free services.** No billing account = no APIs, even free ones.
4. **One account per `gcloud` command.** If you switch projects later, use `gcloud config set project <PROJECT_ID>` explicitly.
5. **`gcloud` auth is cached locally.** If you switch Google accounts in your browser, your CLI may still use the old account. Use `gcloud auth login` to re-auth.

---

## GCP IAM (Identity & Access Management)

### What It Is
IAM is GCP's permission system. It controls **who** (service accounts, user accounts, groups) can do **what** (create resources, read data, delete VMs) on **which resources** (specific projects, services, or individual resources). Permissions are bundled into **roles** — pre-made sets of related permissions.

### Why It's Used Here
We'll create service accounts for our Cloud Run app to interact with Firestore and Cloud Storage without hardcoding credentials. Understanding IAM is essential to not give applications too many permissions (security) or too few (breakage).

### Key Concepts

**User Account:** You (manishwvn998@gmail.com). Logs in via Google account. Has permissions on projects/resources.

**Service Account:** A non-human account (e.g., `myapp@gcp-genai-banking.iam.gserviceaccount.com`). Used by applications to authenticate to GCP APIs. Cannot log in interactively; uses a private key.

**Role:** A bundle of permissions. Examples:
- `roles/editor` — full access to everything in a project.
- `roles/viewer` — read-only access.
- `roles/storage.admin` — full Cloud Storage admin rights.
- `roles/firestore.user` — read/write Firestore data.

**IAM Binding:** Links a user/service account to a role on a resource (project or individual service). Syntax: "Grant `roles/viewer` to `user:you@email.com` on project `gcp-genai-banking`."

### Implementation Snippets

**Create a service account (we'll do this later):**
```bash
gcloud iam service-accounts create myapp --display-name="My App Service Account"
```

**Grant a role to a service account:**
```bash
gcloud projects add-iam-policy-binding gcp-genai-banking \
  --member=serviceAccount:myapp@gcp-genai-banking.iam.gserviceaccount.com \
  --role=roles/editor
```

**List service accounts in a project:**
```bash
gcloud iam service-accounts list --project=gcp-genai-banking
```

### ELI5 Explanation

Think of IAM like **key cards in a building:**
- A **user account** is you with your personal key card.
- A **service account** is a robot with its own key card. Your app tells the robot, "Go fetch data from the database," and the robot uses its key card to prove it has permission.
- A **role** is a label on the key card that says what doors it opens (e.g., "can read storage" or "can write to database").
- An **IAM binding** is the act of handing the robot its key card and saying, "This key opens these doors."

### Common Gotchas

1. **Service account keys are secrets.** If a key leaks, anyone can impersonate your app. Rotate keys regularly.
2. **Overpermissioning is a security risk.** Don't give `roles/editor` to everything. Use the narrowest role needed.
3. **IAM changes take a few seconds to propagate.** After granting a role, wait a moment before using it.

---

## IAM Deep-Dive (Service Accounts & Roles)

### What It Is
Zoom-in on service accounts specifically — non-human accounts apps use to auth to GCP APIs without hardcoding secrets. Builds on [GCP IAM](#gcp-iam-identity--access-management) above.

### Why It's Used Here
`filings-rag-app` service account is what the Cloud Run app uses to talk to Firestore + Cloud Storage. App code never holds user credentials — it holds a service account key (or, in prod, Cloud Run's attached identity) scoped to only what it needs.

### Key Concepts

**User account vs. service account:** user account = you, logs in interactively. Service account = robot identity, no interactive login, auths via key file or attached identity.

**Role:** bundle of permissions. Granted at project, folder, org, or resource level.

**IAM binding:** the link between a member (user/service account) and a role on a resource.

**Principle of least privilege:** grant only permissions actually needed. Not `roles/editor` for everything — narrow, service-specific roles instead.

### Implementation Snippets

**Create service account:**
```bash
gcloud iam service-accounts create filings-rag-app \
  --display-name="Filings RAG App Service Account"
```

**List service accounts:**
```bash
gcloud iam service-accounts list --project=gcp-genai-banking
```

**Assign roles (Firestore + Cloud Storage):**
```bash
gcloud projects add-iam-policy-binding gcp-genai-banking \
  --member="serviceAccount:filings-rag-app@gcp-genai-banking.iam.gserviceaccount.com" \
  --role="roles/datastore.user"

gcloud projects add-iam-policy-binding gcp-genai-banking \
  --member="serviceAccount:filings-rag-app@gcp-genai-banking.iam.gserviceaccount.com" \
  --role="roles/storage.objectViewer"
```

Note: `roles/firestore.user` / `roles/firestore.editor` do NOT exist at project-binding level — use `roles/datastore.user` (Firestore in Native mode runs on the Datastore API, IAM roles inherited from there).

**Create and download a key:**
```bash
gcloud iam service-accounts keys create filings-rag-app-key.json \
  --iam-account=filings-rag-app@gcp-genai-banking.iam.gserviceaccount.com
```

### ELI5 Explanation

Service account = robot key card. Robot (app) can't log in like a person, so you hand it a card (key file) pre-programmed to open only the doors it needs (Firestore room, Storage room) — not the whole building.

### Common Gotchas

1. **`roles/firestore.user`/`roles/firestore.editor` don't exist at project level.** Use `roles/datastore.user` instead — hit this directly during setup.
2. **Service account keys are secrets.** Never commit to git. Gitignore the `.json` key file.
3. **IAM changes take a few seconds to propagate.** Don't panic if a fresh binding doesn't work instantly.
4. **Prefer narrow roles over broad ones.** `datastore.user` + `storage.objectViewer`, not `roles/editor`, even though editor is "easier."

---

## Cloud Storage

### What It Is
GCP's object storage service — like a giant, durable file system in the cloud. You create **buckets** (containers), upload **objects** (files), and retrieve them by name. Unlike a filesystem, there's no folder hierarchy — just prefix naming.

### Why It's Used Here
Phase 1: ingest SEC filing PDFs and earnings transcripts into Cloud Storage, then process them (chunk, embed) in a Cloud Run service. Always-Free tier: 5 GB storage + 5K Class A ops + 50K Class B ops per month (enough to ingest hundreds of documents).

### Key Concepts

**Bucket:** A named container for objects. Bucket names are globally unique across all of GCP. Must be lowercase, alphanumeric, hyphens OK, 3–63 chars.

**Object:** A file stored in a bucket. Accessed by its key (path/name). Each object has metadata (size, content-type, creation date, custom metadata).

**Regions:** Buckets are created in a region (e.g., `us-central1`). Always-Free tier only applies to `us-east1`, `us-west1`, `us-central1`.

**Class A vs. Class B operations:**
- **Class A** — writes, list operations. Always-Free: 5,000/month.
- **Class B** — reads, other operations. Always-Free: 50,000/month.
- Over-quota ops are billed.

### Implementation Snippets

**Create a bucket (we'll do this in Phase 1):**
```bash
gcloud storage buckets create gs://gcp-genai-banking-filings --location=us-central1 --uniform-bucket-level-access
```

**Upload a file:**
```bash
gcloud storage cp local-file.pdf gs://gcp-genai-banking-filings/filings/
```

**List objects in a bucket:**
```bash
gcloud storage ls gs://gcp-genai-banking-filings/
```

### ELI5 Explanation

Cloud Storage is like **a massive warehouse where you rent shelf space.**
- A **bucket** is one shelf.
- An **object** is a box on that shelf (the file).
- You can put thousands of boxes on one shelf; you find them by their label (the object key/name).
- Unlike a filing cabinet with folders, there's no true hierarchy — just naming patterns that *look* like folders (e.g., `filings/sec/2024/10k.pdf` is just a long name, not a folder).

### Common Gotchas

1. **Bucket names are globally unique.** If someone else took `gcp-genai-banking-filings`, you can't use it. Be creative with the name.
2. **Always-Free storage only in 3 US regions.** Uploading to `europe-west1` silently incurs charges.
3. **Class A operations are pricier.** Listing 1,000 files = 1,000 Class A ops. Batch your lists.
4. **Egress costs.** Downloading data *out* of GCP (e.g., to your laptop) is charged at $0.12/GiB/month for most destinations. Stay under 100 GB/month to be free-tier safe.

---

## Firestore (Cloud Firestore)

### What It Is
A managed NoSQL database (document/collection model). Data is stored as **documents** (JSON-like records) in **collections** (like tables). Firestore is real-time, scalable, and as of 2026, supports native **vector search** for RAG/similarity matching.

### Why It's Used Here
- **Phase 1:** Store document metadata (title, source, upload date) and their embeddings (vectors).
- **Phase 2:** KYC extraction results, flagged transactions, and verification audit logs. In an agentic architecture, Firestore's role expands beyond single-purpose RAG storage to become **shared memory across multiple agents** — the supervisor, KYC-extraction, and fraud-explainer agents can all read/write the same Firestore project using their own collections (e.g. `kyc_documents`, `fraud_flags`) alongside `filings_chunks`. Firestore's flexible document model also suits persisting evolving agent state (what's been retrieved, what tools have run, intermediate results) between steps in a LangGraph flow — no new infrastructure needed, same database, more collections and consumers.
- **Vector search:** Query documents by semantic similarity — the core of RAG retrieval.
- **Always-Free tier:** 1 GiB storage, 50K reads / 20K writes / 20K deletes per day — plenty for an MVP.

### Key Concepts

**Document:** A single record (like a row in SQL). Contains fields (key-value pairs). Docs are versioned and timestamped.

**Collection:** A grouping of documents (like a table). Can be top-level or nested under another document (subcollections). Unlike a SQL table, a Firestore collection enforces no fixed schema — two documents in the same collection can have entirely different fields.

**Vector field:** A field that stores a dense embedding (list of floats). Firestore indexes these for KNN (K-nearest neighbor) search. Dimension can be up to 2048 (common: 768 for many embedding models).

**Vector search:** Query: "Find docs similar to this vector." Firestore returns the K closest neighbors by distance (cosine, Euclidean, dot product). Cosine distance measures the **angle** between two vectors (semantic direction), not their magnitude/length — two vectors pointing in a similar "direction" in meaning-space have low distance (0 = identical) regardless of how long either vector is. In this project: real example distances were 0.2366 (high relevance), 0.3828 (good relevance), and 0.5502–0.5505 (weak/irrelevant matches).

**Real-time listeners:** You can subscribe to live updates — if a document changes, your app is notified immediately.

### How to Query Firestore

Firestore can be accessed via three different paths, each with different capabilities:

| Access Path | What it does | What it CANNOT do |
|---|---|---|
| **GCP Console** | Browse documents; apply simple equality/range filters via Data tab query builder | Vector similarity search (`find_nearest`); complex queries |
| **gcloud CLI** | Manage infrastructure: create/delete databases, create vector indexes, check index status, manage backups | Query document data at all — gcloud is infrastructure/admin only, not for reading app data |
| **Application code (Python client library)** | Full query power: simple `.where()` filters, complex `find_nearest()` vector similarity search, transactions | None — this is the most capable path |

**Important:** A common gotcha is trying to query data via `gcloud` CLI (e.g., `gcloud firestore documents list`). While this command *looks* like it should work, `gcloud` is fundamentally an infrastructure management tool, not a data-query tool. For actual data access, always use application code (Python client library) or the Console UI for simple browsing.

### Implementation Snippets

We'll do these in Claude Code Phase 1, but here's the concept:

**Initialize Firestore (Python):**
```python
from google.cloud import firestore

db = firestore.Client(project="gcp-genai-banking")
```

**Add a document with an embedding:**

Note: as of google-cloud-firestore 2.27.0, Vector is not exported at the top-level `firestore` namespace — import from firestore_v1.vector directly (see Embedding Generation section for full gotcha).

```python
from google.cloud.firestore_v1.vector import Vector

db.collection("filings").document("10k-2024").set({
    "title": "ACME Corp 10-K 2024",
    "source": "SEC EDGAR",
    "embedding": Vector([0.12, 0.34, -0.56, ...]),  # 768-dim vector
    "uploaded_at": firestore.SERVER_TIMESTAMP
})
```

**Vector search (KNN):**
```python
query_vector = [0.11, 0.35, -0.55, ...]  # Query embedding
results = db.collection("filings").find_nearest(
    vector_field="embedding",
    query_vector=query_vector,
    limit=5,
    distance_measure=firestore.DistanceMeasure.COSINE
).stream()
```

### ELI5 Explanation

Firestore is like **a smart filing cabinet that understands meaning.**
- A **collection** is a drawer (e.g., "filings").
- A **document** is a file folder in that drawer, with labeled tabs inside (fields).
- A **vector field** is one special tab that holds a list of numbers representing the *meaning* of the document.
- **Vector search** is you saying, "Show me all folders that have similar 'meaning' to this one," and the cabinet instantly finds them.

### Common Gotchas

1. **Vector field is not auto-indexed.** You must create a composite index on the vector field before querying — Firestore does this for you the first time you query, but it can take a few minutes.
2. **Reads/writes are charged per document, not per field.** Reading one field from 100 docs = 100 read ops, not 1.
3. **Real-time listeners consume reads.** A live subscription that updates every second = 86,400 reads per day. Good for apps, bad for your quota if you're not careful.
4. **Nested documents don't rollover queries.** If you query a parent collection, you don't automatically get subcollection data.
5. **`distance_result_field` parameter is required for distance scores.** When running `find_nearest`, include `distance_result_field="distance"` in the query to get the similarity score back on each returned document — without it, results only contain the stored fields and no distance metric, making it impossible to gauge retrieval confidence.

### Firestore vs. SQL / Relational Databases

**Key architectural difference:** SQL databases (like PostgreSQL, Cloud SQL) enforce a **fixed schema** — every row in a table has the same columns, with the same data types. Relationships between tables happen via formal joins and foreign keys. Firestore has no fixed schema and no formal inter-table relationships; each document in a collection can have different fields, and collections are isolated from each other.

**Why this matters:**
- **SQL strength:** If you need consistent structure, data integrity via foreign keys, and complex queries across multiple tables (joins), use SQL.
- **Firestore strength:** If your data shape varies (e.g., different documents hold different fields), or if you need schema flexibility as your app evolves, Firestore is simpler.
- **SQL doesn't apply:** Firestore can't run SQL because SQL's core operations (joins, aggregations across tables, enforced schema) don't map onto a document/collection model. This is architectural, not a missing feature.

**Path to SQL if you need it:** GCP offers two SQL-native options for when you need traditional SQL querying:
1. **Cloud SQL** — fully managed PostgreSQL/MySQL — use if your app needs relational structure from day one.
2. **BigQuery** — serverless data warehouse — use if you need SQL-style analytics over Firestore data. Firestore supports **export/sync to BigQuery**, which mirrors your Firestore collections into BigQuery tables; you then run SQL queries against the mirror for reporting/analytics, while your live app keeps using Firestore's flexibility and real-time updates.

**ELI5:** SQL table = identical printed form everyone fills out (fixed columns). Firestore document = a folder where each one can hold different pages/fields. You can photocopy all your Firestore folders into a ledger (BigQuery) and do accounting (SQL) on the ledger without changing the folders.

### Navigating Firestore in the GCP Console (Aug 2026)

Console path: **Databases** (left sidebar under Data) → select your database name → four tabs:

**Data tab:**
- Browse all collections and their documents.
- Vector fields are visually distinguished from regular scalar fields in the document view.
- Simple query builder at top: equality and range filters (NOT vector search — that requires Python code).
- Click a document to view/edit its fields inline.

**Indexes tab:**
1. **Automatic** — indexes Firestore creates on your behalf for simple scalar-field queries (equality, range). Status shown as built or building; refresh the tab to see status updates.
2. **Manual** — indexes you create explicitly for complex queries (composite indexes across multiple fields) AND all vector indexes for `find_nearest`. Vector indexes appear here listed by collection and field.
3. Creating a vector index via Console UI: **Manual tab** → **Create Index** button → Collection: `filings_chunks` → add Field: `embedding` (type: Vector, dimension 768, distance: COSINE) → Create Index. Takes a few minutes; refresh the Indexes tab to see status update.

**Usage tab:**
- Read/write/delete operation counts for the day (resets daily). Compare against your Always-Free quotas (50K reads, 20K writes, 20K deletes/day).
- Useful for spotting quota overages or expensive queries before they consume your limit.

**Rules tab:**
- Security rules for client-side Firebase SDK access (e.g., mobile app using Firebase). Less relevant for server-side-only access patterns (your app authenticated via service account). Reference for context, but not used in Phase 1.

---

## Google AI Studio & Gemini API (Free Tier)

### What It Is
**Google AI Studio** (ai.google.dev) is a playground and free-tier access point for Google's **Gemini API**. You get free usage of Gemini models (text generation, embeddings) up to daily rate limits. This is *separate* from Vertex AI (the managed, paid version on GCP).

### Why It's Used Here
- **Text generation:** Chat with filings, explain transactions, generate structured data.
- **Embeddings:** Convert text into vectors (768-dim) for Firestore vector search.
- **Free tier:** ~1,500 requests/day for Flash/Flash-Lite models, separate free pool from GCP Always-Free.
- **Why not Vertex AI?** Vertex endpoints are billed; AI Studio free tier is not.

### Key Concepts

**API key:** A string you pass to authenticate requests. Created in AI Studio, not tied to GCP IAM. Different from GCP service account keys.

**Rate limits (free tier, as of Aug 2026):**
- **Gemini Flash Latest (`gemini-flash-latest`):** ~15 requests per minute, ~1,500 requests per day. Live-verified in Component 4 as working on free tier.
- **Gemini 2.5 Flash/2.0 Flash-001:** NOT available on free tier this account (tested in Component 4; `gemini-2.5-flash` → 404 "no longer available to new users"; `gemini-2.0-flash-001` → 429 with `limit: 0` on free-tier quota). See Retrieval & Grounded Generation gotchas for full error bodies.
- **Embedding models (gemini-embedding-001):** Free tier, 768-dim output. text-embedding-004/005 no longer served (see Embedding Generation gotchas).
- These limits reset at midnight Pacific Time (PST).

**Request vs. token limits:**
- **RPM/RPD:** How many API calls you can make.
- **TPM:** Tokens per minute. A single request can use many tokens (1 request with 100K token context = 100K tokens).
- You hit RPM limit before TPM in most cases.

**Data privacy:** Google's free tier terms allow Google to use your prompts/outputs to improve models (unless you disable this, which you can't on free tier). Use the free tier for non-sensitive content.

### Implementation Snippets

**Get an API key (free):**
1. Go to https://ai.google.dev
2. Click "Get API key"
3. Select your project (can be any project, not tied to GCP project)
4. Copy the key

**Call Gemini API (Python, we'll do this in Phase 1):**
```python
import google.generativeai as genai

genai.configure(api_key="YOUR_API_KEY")
model = genai.GenerativeModel("gemini-2.5-flash")
response = model.generate_content("What is a 10-K filing?")
print(response.text)
```

**Generate embeddings:**

text-embedding-004/005 are no longer served as of this project's Aug 2026 build — verified via ListModels, see Embedding Generation section.

```python
response = genai.embed_content(
    model="gemini-embedding-001",
    content="SEC filing summary text here...",
    config={"output_dimensionality": 768}
)
embedding = response.embeddings[0].values  # List of 768 floats
```

### ELI5 Explanation

AI Studio is like **having a free talking oracle at your fingertips.**
- You ask it questions (generate text) or ask it to translate words into numbers (embeddings).
- An **API key** is your VIP pass that lets you call the oracle remotely (from your code).
- You get a **budget per day** (1,500 calls). Once you hit it, you have to wait until tomorrow to call again.
- The oracle listens to everyone for free, so it may remember your questions to get smarter (that's why you don't send secrets).

### Common Gotchas

1. **Rate limits are per project, per API key, but the limit is still enforced.** Making 10 API keys in the same project doesn't give you 10× the quota.
2. **Free tier prompts are used for model improvement.** Don't send proprietary/sensitive data.
3. **Embedding models vary in dimension.** `text-embedding-005` produces 768-dim vectors. Make sure Firestore index matches.
4. **API key shows up in your code — keep it secret.** Use environment variables or Secret Manager in production (we'll do this in Phase 1).

---

## GCP Always-Free vs. AI Studio Free Tier — Separate Projects Required

### What It Is
GCP's Always-Free tier and Google AI Studio's Gemini API free tier are *independent quota systems*, not just different rate limits. Critically, **billing account status determines which tier a Gemini API key falls into** — a key created under a project with billing linked automatically gets promoted to Tier 1/Postpay, even if you never use it.

### Why It's Used Here
Our app needs GCP Always-Free services (Firestore, Storage, Cloud Run) which require a billing account linked to the project. But that same billing link automatically promotes any Gemini API key created under that project to paid tier. To stay on free tier for embeddings, we maintain two projects.

### Key Concepts

**Billing tier determination:**
- **Free tier:** Gemini API key created under a project with NO billing account attached.
- **Tier 1 (Postpay):** Gemini API key created under a project WITH billing account linked.
- This is automatic — there is no "opt-out" setting on the key itself or in the AI Studio UI.

**Why separate projects?**
- Main project (`gcp-genai-banking`): Has billing linked, enables GCP Always-Free services (Firestore, Storage, Cloud Run).
- Secondary project (`gcp-genai-llm-free`): No billing account, never attach one — this is where the free-tier Gemini key lives.
- Active project stays gcp-genai-banking; the secondary project is only used to hold the API key (can be referenced with `--project` flag or in code).

### Implementation Snippets

**Create billing-free project:**
```bash
gcloud projects create gcp-genai-llm-free --name="Gemini API Free Tier"
# Do NOT link billing to this project
```

**Verify no billing is linked:**
```bash
gcloud billing projects list
# gcp-genai-llm-free should NOT appear in the output
```

**Create free-tier API key (in the secondary project):**
```bash
# In AI Studio (ai.google.dev), when creating the API key, select gcp-genai-llm-free from the project dropdown
# Verify "Free tier" badge appears (Tier 1 / Postpay would appear if you accidentally used gcp-genai-banking)
```

### ELI5 Explanation

It's like **having two mailboxes — one for bills (GCP services) and one that's permanently unlisted (Gemini API free key).**
- You can't slap a "do not bill" sticker on the main mailbox and expect it to work; the postman follows project-level rules, not stickers.
- So you rent a second mailbox that was never on any subscription list in the first place, and use that one for the free service.
- Both projects are yours; you just keep them separate by design.

### Common Gotchas

1. **"Buy credits" prompt is not a status check.** If you click into an API key's billing settings in AI Studio and see a "Buy prepaid credits" button, that's a *real* purchase flow — not informational. The key is on Tier 1 (postpay). Close the dialog; don't proceed. Create a new key under the billing-free project instead.
2. **Billing link is project-level, not per-API-key.** You cannot "un-promote" a key created under a billing-linked project by changing its settings — it's locked to Tier 1 because of the project. Delete the key and create a new one under the billing-free project.
3. **Default project matters.** If your `gcloud` default is set to `gcp-genai-banking`, and you create an API key in AI Studio without explicitly selecting a project, it defaults to gcp-genai-banking and lands on Tier 1. Always verify the project selector in AI Studio before generating a key.
4. **No need to switch active projects constantly.** The secondary project exists only to host the API key; your Cloud Run app (deployed from gcp-genai-banking) pulls the key from .env and uses it to call Gemini. No CLI switching needed.

---

## Cloud Run

### What It Is
A serverless compute platform — you deploy a containerized app (Docker image), and GCP runs it on-demand, scaling to zero when idle. You pay only for requests + CPU/memory used. Always-Free tier: 2M requests/month.

### Why It's Used Here
Hosts the web service for the Filings RAG chatbot. Receives user queries, retrieves from Firestore, calls Gemini, returns grounded responses. Scales automatically; no server management.

### Key Concepts

**Container/Docker image:** A package that includes your app, runtime, and dependencies. Cloud Run needs this.

**Service:** A deployed container running on Cloud Run. You access it via a unique HTTPS URL. Scales up/down based on traffic.

**Region:** Where the service runs. Always-Free tier applies to `us-central1`, `us-west1`, `us-east1`.

**Concurrency:** How many requests a single instance can handle simultaneously. Default is usually reasonable.

### Implementation Snippets

We'll build this in Phase 1, but the general flow:

```bash
# Build and deploy
gcloud run deploy filings-rag \
  --source=. \
  --region=us-central1 \
  --allow-unauthenticated
```

Your app needs a `Dockerfile`:
```dockerfile
FROM python:3.11
WORKDIR /app
COPY . .
RUN pip install -r requirements.txt
CMD ["gunicorn", "-b", "0.0.0.0:8080", "app:app"]
```

### ELI5 Explanation

Cloud Run is like **a restaurant that only opens when someone orders.**
- You prepare a recipe (code) and package it in a box (Docker image).
- You give the box to Cloud Run; it sets up a kitchen (service).
- When someone orders (makes a request), the kitchen cooks. When orders stop, the kitchen closes (scales to zero).
- You pay only for the meals served (requests), not for keeping the kitchen open 24/7.

### Common Gotchas

1. **Cold start latency.** First request after idle takes longer (container spins up). Subsequent requests are fast.
2. **Always-Free tier has limits.** 2M requests/month is ~67K/day. High-traffic apps will exceed this.
3. **Logs are limited.** Cloud Run only keeps logs for a short time (1 hour for standard, longer for Cloud Logging).
4. **Memory/CPU defaults matter.** Default is 256 MB RAM. Document processing might need more; upgrading costs.

---

## LangChain / LangGraph (Agentic Orchestration)

### What It Is
Frameworks for building AI applications. **LangChain** handles chains (sequences of LLM calls + retrieval). **LangGraph** adds state machines and multi-agent orchestration (agents that call other agents, with controlled loops).

### Why It's Used Here
- **Phase 1 (LangChain):** Chain together document retrieval + Gemini generation.
- **Phase 2 (LangGraph):** Multi-agent supervisor that routes user queries to the right specialist (filings RAG agent, KYC extraction agent, fraud explainer agent).

### Key Concepts

**Chain:** A sequence of operations. E.g., "retrieve similar docs → format prompt → call LLM → return answer." Reusable, testable.

**Agent:** An entity that can reason, plan, and call tools. E.g., "I need to answer this question; let me search the knowledge base, then think about it, then respond."

**Tool:** A function an agent can call. E.g., Firestore vector search is a tool; Gemini API is a tool.

**LangGraph state:** Explicit state passed through the graph. E.g., `{"query": "...", "retrieved_docs": [...], "response": "..."}`.

### Implementation Snippets

We'll build these in Phase 1/2, but concepts:

**Simple chain (LangChain):**
```python
from langchain import PromptTemplate, LLMChain
from langchain_google_genai import ChatGoogleGenerativeAI

llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", api_key=os.getenv("GEMINI_API_KEY"))

prompt = PromptTemplate(
    input_variables=["filing_text"],
    template="Summarize this filing: {filing_text}"
)

chain = LLMChain(llm=llm, prompt=prompt)
result = chain.run(filing_text="...")
```

**Agent with tools (LangGraph):**
```python
from langgraph.graph import StateGraph
from langchain_core.tools import tool

@tool
def retrieve_filings(query: str) -> list:
    """Retrieve similar filings from Firestore vector search."""
    # Implementation here
    pass

# Later: define agent that uses this tool, with state management
```

### ELI5 Explanation

LangChain/LangGraph are like **instruction manuals for your app's brain.**
- A **chain** is a recipe: "Step 1: look up docs, Step 2: ask the AI, Step 3: format response."
- An **agent** is a smarter version: "I have tools; I'll figure out which to use and in what order to answer this question."
- **LangGraph** is orchestration: "I have three agents; based on the question, route to the right one, get the answer, format it nicely."

### Common Gotchas

1. **LangChain abstractions can hide costs.** Each call to an LLM or retrieval tool consumes quota. Easy to overshoot limits without realizing.
2. **State explosion in graphs.** If you're not careful with state shape, you end up passing huge objects between nodes.
3. **Tool validation is your job.** LangChain doesn't validate that a tool call succeeded; you must check.

---

## Production Practices & Workflows

### Environment Management (`uv` / venv)
We'll use **`uv`** for dependency locking and virtual environments — faster and more reproducible than plain `pip`. 

**Why:** Ensures everyone (you, CI/CD, production) runs the same dependency versions. Prevents "works on my machine" surprises.

**Workflow:**
```bash
# Install uv (one-time)
brew install uv  # on macOS

# Create venv
uv venv

# Activate
source .venv/bin/activate

# Add dependencies
uv add google-cloud-firestore google-cloud-storage langchain

# Lock
uv lock

# CI/CD installs from lock
uv sync
```

### Secrets Management
**Never hardcode secrets.** Options:
- **Local dev:** `.env` file (gitignored), load via `python-dotenv`.
- **Production (Cloud Run):** GCP Secret Manager, referenced via IAM. Cloud Run auto-injects as environment variables.

**Snippet:**
```python
# .env (local)
GEMINI_API_KEY=abc123xyz
FIRESTORE_PROJECT=gcp-genai-banking

# main.py
import os
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")
```

### Git & Version Control
Commit from day one. Meaningful messages. Structure:
```
gcp-genai-banking/
├── .env (gitignored)
├── .gitignore
├── README.md
├── requirements.txt (or pyproject.toml if using uv)
├── src/
│   └── copilot/
│       ├── __init__.py
│       ├── embeddings.py
│       ├── retrieval.py
│       └── chat.py
├── tests/
│   └── test_retrieval.py
└── Dockerfile (for Cloud Run)
```

### Common Gotchas

1. **Don't commit `.env`.** Add to `.gitignore`.
2. **Lock file must be committed.** `uv.lock` goes in the repo so CI/CD is reproducible.
3. **Dockerfile should be minimal.** Large images slow down Cloud Run cold starts.

---

## Deprecation & Migration Notes

**`google-generativeai` deprecated upstream (as of Aug 2026).** Google recommends `google-genai` as replacement SDK.

- Still works, no breakage — but no more updates/fixes coming.
- Plan: migrate imports and calls to `google-genai` before `embeddings.py` gets its heavy Phase 2 implementation.
- Low-effort swap (API is similar) — better done early before more code depends on old package.

---

## Document Ingestion & Chunking Strategy

**What:** Chunking splits large documents (10-Ks, transcripts) into smaller, retrieval-sized text pieces before embedding.

**Why:** Embeddings represent semantic meaning of a fixed-size piece of text. A full 10-K is too broad — the embedding would blur together dozens of unrelated topics (risk factors, financials, business description), making similarity search useless. Small, focused chunks let retrieval pull back just the passage relevant to a query.

**Key concepts:**
- **Chunk size** — target ~800 tokens per chunk (tunable). Big enough to preserve context, small enough for precise retrieval.
- **Overlap** — ~100 tokens shared between consecutive chunks, so a sentence split across a chunk boundary doesn't lose surrounding context.
- **Sentence boundaries** — split on `. ` / `! ` / `? ` (regex lookbehind) rather than mid-sentence, so chunks read as coherent text.
- **Token counting** — no tokenizer needed for a rough split; approximate 1 token ≈ 4 characters. Good enough for chunk sizing, not exact.

**Snippets:**

```python
# PDF -> text
import pdfplumber

def read_pdf_text(filepath: str) -> str:
    pages = []
    with pdfplumber.open(filepath) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                pages.append(text)
    return "\n\n".join(pages)
```

```python
# sentence-boundary chunking with overlap
import re

sentences = re.split(r"(?<=[.!?])\s+", text.strip())
# accumulate sentences into ~chunk_size*4 chars, carry last ~overlap*4 chars into next chunk
```

```python
# Firestore chunk document (filings_chunks collection)
from google.cloud.firestore_v1.vector import Vector
from datetime import datetime, timezone

collection.add({
    "text": chunk,
    "source": source_name,
    "source_url": f"local://{filepath}",
    "page_number": 0,
    "chunk_index": index,
    "created_at": datetime.now(timezone.utc),
    "embedding": Vector([0.123, 0.456, -0.789, ...]),  # 768-dim vector, computed externally
})
```

**ELI5:** Chunking is like cutting a book into chapters so you can find the right one quickly, instead of handing someone the whole book and asking them to guess which page has the answer.

**Gotchas:**
1. PDF layout varies wildly — tables, multi-column layouts, and scanned/OCR'd pages can extract as garbled or empty text. Always spot-check extracted text.
2. Overlap is required, not optional — without it, a fact split across a chunk boundary (e.g., a sentence naming a dollar figure) can lose its subject or context entirely.
3. Token counting via char/4 is a rough estimate, not exact — real tokenizers vary by ~20% depending on content (numbers, punctuation tokenize differently than prose).
4. Firestore document size limit is 1MB — chunks should stay well under that (50KB or less is a safe ceiling); at 800 tokens (~3.2KB) per chunk this is a non-issue, but watch for pathological documents with very sparse sentence boundaries.
5. **New GCP project ≠ ready-to-use Firestore.** Two separate setup steps are required before any client code can write: (1) enable the API — `gcloud services enable firestore.googleapis.com --project=<project>`, and (2) create the actual database — `gcloud firestore databases create --location=us-central1 --type=firestore-native --project=<project>` (a project can have the API enabled with zero databases). Skipping either gives a `403 PermissionDenied: SERVICE_DISABLED` error that reads like a permissions/IAM problem but is actually a provisioning problem. Both are one-time, per-project setup — not needed again once done.

---

## Embedding Generation & Vector Indexing

**What:** Converting text (a chunk of a filing) into a dense vector — a fixed-length list of floats — that numerically represents its meaning.

**Why:** Enables retrieval by meaning, not keyword matching. A query about "credit risk exposure" should match a chunk discussing "loan default risk" even with zero shared words, because their embeddings land close together in vector space.

**Critical:** Firestore does not generate embeddings itself — it has no AI model built in. Embedding generation happens entirely externally (via the Gemini API in this project); Firestore's role is purely to store the resulting vector and make it searchable via `find_nearest`.

**Key concepts:**
- **Embedding dimension** — fixed length of the vector (768 here). Firestore's vector index is dimension-locked; the index and every stored vector must match.
- **Idempotent re-runs matter** — embedding calls cost API quota (rate-limited on free tier). `embed_filings.py` checks for an existing `embedding` field before calling the API, so re-running the script after a partial failure or adding new chunks doesn't burn quota re-embedding chunks already done.
- **Rate limiting** — Gemini free tier caps requests per minute at the project level. A fixed delay between calls (5 sec here, conservative vs. ~4 sec at 15 RPM) avoids 429s outright rather than relying on retry-after-failure.
- **Vector index requirement** — Firestore does not auto-index vector fields for KNN search. A composite index must be explicitly created (`gcloud firestore indexes composite create ...`) before `find_nearest` queries will work; without it, queries fail even though the data is there.

**Snippets:**

```python
# embed_text — retry with exponential backoff, fails loudly after MAX_RETRIES
def embed_text(text: str) -> list:
    client = _get_client()
    for attempt in range(MAX_RETRIES):
        try:
            response = client.models.embed_content(
                model="gemini-embedding-001",
                contents=text,
                config=types.EmbedContentConfig(output_dimensionality=768),
            )
            return response.embeddings[0].values
        except Exception as e:
            if attempt < MAX_RETRIES - 1:
                time.sleep(BACKOFF_BASE_SECONDS * (2 ** attempt))
            else:
                raise RuntimeError(f"embed_text failed after {MAX_RETRIES} attempts: {e}") from e
```

```bash
# Firestore vector composite index — required before find_nearest works
gcloud firestore indexes composite create \
  --collection-group=filings_chunks \
  --query-scope=COLLECTION \
  --field-config field-path=embedding,vector-config='{"dimension":"768", "flat": "{}"}' \
  --database="(default)"
```

```python
# google-generativeai (deprecated) -> google-genai (current)
# old: import google.generativeai as genai; genai.configure(api_key=...)
# new:
from google import genai
from google.genai import types

client = genai.Client(api_key=api_key)
response = client.models.embed_content(
    model="gemini-embedding-001",
    contents=text,
    config=types.EmbedContentConfig(output_dimensionality=768),
)
vector = response.embeddings[0].values  # list[float], length 768
```

**ELI5:** Embeddings are like giving every sentence a GPS coordinate in "meaning-space" — sentences about similar topics end up near each other, so finding "similar meaning" becomes finding "nearby coordinates."

**Gotchas:**
1. `google-generativeai` is deprecated — use `google-genai` (`from google import genai`). Client instantiation and call shape both changed (`genai.Client(api_key=...)`, `client.models.embed_content(...)`), not just the import path.
2. `gemini-embedding-001` defaults to 3072 dimensions — pass `config=types.EmbedContentConfig(output_dimensionality=768)` explicitly to match Firestore's index dimension. `text-embedding-004` (referenced in earlier plans) is no longer served by the API — `ListModels` is the source of truth for current model names.
3. The vector index must exist *before* `find_nearest` queries work — Firestore doesn't build it implicitly on first query for vector fields (unlike some scalar-field indexes). Creating it is async and can take a few minutes; check with `gcloud firestore indexes composite list`.
4. Re-running embedding scripts should always skip chunks that already have an `embedding` field — free-tier rate limits (RPM) are project-wide, not per-key, so wasted re-embeds eat into the same shared quota as everything else hitting the project.
5. `firestore.Vector` (the top-level import path documented above in the Firestore section) doesn't exist on `google-cloud-firestore==2.27.0` — the installed version doesn't re-export `Vector` at the package root. Actual working import: `from google.cloud.firestore_v1.vector import Vector`. Likely cause: Google's docs/examples reflect a different client library version than what's currently pinned here — always verify with `dir(module)` or a quick import check rather than trusting doc snippets verbatim against an installed version.

---

## Retrieval & Grounded Generation (RAG Chain)

**What:** Combining semantic retrieval (find the most relevant filing chunks for a question) with constrained generation (make the model answer only from those chunks). Two-stage pipeline: `retrieve_relevant_chunks()` embeds the question and runs `find_nearest` against Firestore; `generate_grounded_answer()` feeds the retrieved text into a tightly-scoped prompt and attaches citations in code.

**Why:** Grounding prevents hallucination. Left alone, an LLM will answer confidently from parametric knowledge even when the real filing says nothing on the topic — dangerous in a banking-domain interview demo. Two separate guardrails matter here: (1) a prompt instruction telling the model to refuse when the context doesn't cover the question, and (2) citations attached programmatically from the actual retrieved chunk metadata, not parsed/trusted from the model's own `[1]`-style references in its text. The model can lie about what it used; the retrieval code can't.

**Key concepts:**
- *Distance/similarity scores* — `find_nearest` with `DistanceMeasure.COSINE` returns cosine distance (lower = more similar). Surfacing this in citations gives transparency into how confident the match was, useful for debugging bad retrieval before blaming generation.
- *top_k tradeoffs* — more chunks = more context = costlier prompt + more chance of irrelevant text diluting the answer; too few chunks = real answer might be split across chunks not retrieved. `top_k=4` picked as a reasonable default for short filing excerpts; tune per corpus.
- *Prompt-based grounding constraints* — the prompt explicitly enumerates the refusal string verbatim and forbids outside knowledge. This is necessary but not sufficient (models don't always obey), which is why programmatic citations exist as the trustworthy layer.
- *Programmatic vs. model-reported citations* — citations are built directly from `retrieved_chunks` metadata (`source`, `chunk_index`, `distance`) regardless of whether the model's answer text contains `[1]`/`[2]` markers. This means citations always reflect what was actually retrieved and sent to the model, not what the model claims it used.
- *This is not automated eval* — no scoring, no labeled question/answer pairs, no precision/recall on retrieval, no LLM-judge grading of answer quality. Manual spot-check only (one grounded query, one refusal query). Formal RAG evaluation (retrieval metrics, groundedness scoring, a verifier/LangGraph agent) is explicit **Phase 2 scope**.

**Snippets:**
```python
# retrieve_relevant_chunks — src/copilot/retrieval.py
query_vector = Vector(embed_text(question))
vector_query = collection.find_nearest(
    vector_field="embedding",
    query_vector=query_vector,
    distance_measure=DistanceMeasure.COSINE,
    limit=top_k,
    distance_result_field="distance",
)
```
```python
# grounding prompt template — src/copilot/rag_chain.py
"Answer ONLY using the provided context. If the answer is not present in "
"the context, respond exactly: 'I don't have enough information in the "
"available documents to answer this.' Do not use outside knowledge. When "
"you state a fact, reference which context number it came from, like [1]."
```
```python
# citation attachment — independent of model output text
citations = [
    {"source": c["source"], "chunk_index": c["chunk_index"], "distance": c["distance"]}
    for c in retrieved_chunks
]
```

**ELI5:** Grounding is like an open-book exam where the student can only write answers using page numbers they actually cite — if it's not on the page, they have to say "not in the book" instead of making something up. The teacher (our code) doesn't trust the student's claimed page numbers either — it independently writes down which pages were handed to the student, so it always knows the true source regardless of what the student wrote.

**Gotchas:**
1. Model name needed live verification, not assumption. Distinction from the Component 2 embedding gotcha (`text-embedding-004` simply didn't appear in `ListModels` at all — a "this model doesn't exist for you" case): here, **both `gemini-2.5-flash` and `gemini-2.0-flash-001` DID appear in `ListModels` output with `generateContent` in their supported actions** — listing said they were usable — but the actual `generate_content` call failed for each, via two *independent* gates, not the same failure twice:
   - `gemini-2.5-flash` → **404 NOT_FOUND, "no longer available to new users."** This is an **account-based access restriction** — sunset for new accounts/keys, unrelated to quota or tier. No amount of paid billing fixes this; the model is simply gone for this account. Full raw error body:
     ```
     google.genai.errors.ClientError: 404 NOT_FOUND. {'error': {'code': 404, 'message': 'This model models/gemini-2.5-flash is no longer available to new users. Please update your code to use a newer model for the latest features and improvements.', 'status': 'NOT_FOUND'}}
     ```
   - `gemini-2.0-flash-001` → **429 RESOURCE_EXHAUSTED, `limit: 0` on `generate_content_free_tier_requests`.** This is a **per-model free-tier quota set to zero**, not ordinary rate-limiting — free tier gets none of this model at all, at any request rate. Paid tier would likely work fine (the quota is a free-tier allocation, not a hard model restriction). Full raw error body:
     ```
     google.genai.errors.ClientError: 429 RESOURCE_EXHAUSTED. {'error': {'code': 429, 'message': 'You exceeded your current quota, please check your plan and billing details. For more information on this error, head to: https://ai.google.dev/gemini-api/docs/rate-limits. To monitor your current usage, head to: https://ai.dev/rate-limit. \n* Quota exceeded for metric: generativelanguage.googleapis.com/generate_content_free_tier_requests, limit: 0, model: gemini-2.0-flash\n* Quota exceeded for metric: generativelanguage.googleapis.com/generate_content_free_tier_requests, limit: 0, model: gemini-2.0-flash\n* Quota exceeded for metric: generativelanguage.googleapis.com/generate_content_free_tier_input_token_count, limit: 0, model: gemini-2.0-flash\nPlease retry in 9.399140862s.', 'status': 'RESOURCE_EXHAUSTED', 'details': [{'@type': 'type.googleapis.com/google.rpc.Help', 'links': [{'description': 'Learn more about Gemini API quotas', 'url': 'https://ai.google.dev/gemini-api/docs/rate-limits'}]}, {'@type': 'type.googleapis.com/google.rpc.QuotaFailure', 'violations': [{'quotaMetric': 'generativelanguage.googleapis.com/generate_content_free_tier_requests', 'quotaId': 'GenerateRequestsPerDayPerProjectPerModel-FreeTier', 'quotaDimensions': {'location': 'global', 'model': 'gemini-2.0-flash'}}, {'quotaMetric': 'generativelanguage.googleapis.com/generate_content_free_tier_requests', 'quotaId': 'GenerateRequestsPerMinutePerProjectPerModel-FreeTier', 'quotaDimensions': {'location': 'global', 'model': 'gemini-2.0-flash'}}, {'quotaMetric': 'generativelanguage.googleapis.com/generate_content_free_tier_input_token_count', 'quotaId': 'GenerateContentInputTokensPerModelPerMinute-FreeTier', 'quotaDimensions': {'location': 'global', 'model': 'gemini-2.0-flash'}}]}, {'@type': 'type.googleapis.com/google.rpc.RetryInfo', 'retryDelay': '9s'}]}}
     ```
   - `gemini-flash-latest` → **worked.** Nonzero free-tier quota, no account-level access restriction. This is the model actually in use (`src/copilot/rag_chain.py`).
   Generalizable lesson: **`ListModels` only confirms a model exists in the API surface — it does NOT confirm your account/tier can call it.** Two independent gates sit between "listed" and "callable": (1) account-level access restrictions (model sunset for new users/keys — 404), and (2) per-model free-tier quota, which can be set to exactly zero for a given model regardless of overall API usage (429, `limit: 0`). Neither shows up in `ListModels`. Always verify with a live minimal `generate_content` call before committing to a model choice — don't infer callability from listing alone.
2. `find_nearest` requires `distance_result_field` kwarg to get the similarity score back on each returned doc — without it, results only contain the stored fields, no distance.
3. Refusal path still returns retrieved-chunk citations (the search still ran and found *something*, just nothing relevant) — this is intentional per the "attach whatever was retrieved" design, but worth noting the refusal response's citations show what was searched, not what was used to answer. To make this unambiguous to any caller, `generate_grounded_answer()` also returns `answer_grounded: bool` — `False` whenever the answer text equals the exact refusal string (whether because no chunks were retrieved at all, or because chunks were retrieved but the model judged them irrelevant and refused anyway). `True` means the model actually answered from context. Check this field, not just whether `citations` is non-empty, to tell "grounded with sources" apart from "searched but found nothing usable."

---

## Web APIs & HTTP Fundamentals

### What It Is

An **API** (Application Programming Interface) is a defined contract for software-to-software requests. **HTTP** is the protocol used by web APIs — it defines methods (GET, POST, PUT, DELETE, etc.), endpoints (URLs), request/response bodies (data formats), and status codes (responses: 200 OK, 404 Not Found, 429 Too Many Requests, 500 Server Error, etc.). 

### Why It's Used Here

The `rag_query()` Python function works locally in Python only. To expose it beyond a single developer's laptop — to a browser, a curl command, a mobile app, or a frontend UI — we need an HTTP interface. That interface will be a web API.

### Key Concepts

**HTTP Methods:**
- **GET** — retrieve data, safe (no side effects), idempotent (same result each time).
- **POST** — submit data to create/change state, causes side effects, not idempotent.
- **PUT/PATCH** — update existing resources.
- **DELETE** — remove resources.

**Request/Response Bodies:**
- Request body contains data sent to the server (usually JSON).
- Response body contains data sent back (status code + response body, e.g., answer + citations).

**Status Codes:**
- **2xx** (200, 201) — success.
- **4xx** (400 bad request, 401 unauthorized, 404 not found, 429 rate limited) — client error.
- **5xx** (500 internal server error) — server error.

### Implementation Snippets

**Conceptual HTTP request:**
```
POST /query HTTP/1.1
Host: api.example.com
Content-Type: application/json

{
  "question": "What are ACME's main financial risks?"
}
```

**Response:**
```
HTTP/1.1 200 OK
Content-Type: application/json

{
  "answer": "...",
  "answer_grounded": true,
  "citations": [...]
}
```

### ELI5 Explanation

Think of an HTTP API like a **restaurant transaction:**
- You walk in, look at a **menu (endpoints)** — fixed options like "GET /menu" or "POST /order".
- You place an order with details (request body) — "I want a sandwich, extra pickles."
- The kitchen receives it, cooks, and sends back a plate (response) — "Here's your sandwich" (200 OK) or "We're out of pickles" (400 Bad Request).
- You never see the kitchen internals; you only use the menu and the plate that comes back.

### Common Gotchas

1. **Endpoint design matters.** `/api/query` returning different data per HTTP method (GET = list queries, POST = submit new query) uses HTTP correctly; non-idiomatic designs (everything POST, ignoring method semantics) work but confuse future readers.
2. **Status codes are semantic.** Return 201 Created for POST that creates, 404 for a missing resource, 429 for rate-limit, not just 200 for everything. Clients parse these.
3. **Request/response validation is the boundary.** Never trust incoming JSON — validate shape, types, required fields. Outgoing response should also be validated before serializing.

---

## FastAPI Framework

### What It Is

**FastAPI** is a Python web framework for building HTTP APIs quickly. It automatically handles HTTP routing (mapping endpoints to Python functions), request parsing (converting JSON to Python objects), response serialization (converting Python objects back to JSON), and generates interactive API documentation (OpenAPI/Swagger at `/docs` and `/redoc`).

### Why It's Used Here

Without a framework, building an HTTP endpoint requires low-level HTTP plumbing (socket handling, parsing headers, serializing responses). FastAPI handles all that. Beyond convenience, it provides **automatic request/response validation via Pydantic models** — define the shape of incoming data once, and invalid requests are rejected before hitting your code. For an interview demo, the auto-generated `/docs` (interactive Swagger UI) is a polished artifact that showcases the API without writing a separate spec.

### Key Concepts

**Pydantic Models:**
- Python dataclasses-like objects that validate data shape, types, and constraints.
- `@app.post("/query", response_model=QueryResponse)` means: accept a `QueryRequest` body, run your function, return a `QueryResponse` — FastAPI validates both.

**Decorators:**
- `@app.get(...)`, `@app.post(...)` map HTTP methods and paths to Python functions.

**Dependency Injection:**
- FastAPI can pass database connections, config, logged-in user, etc. as function arguments — framework handles plumbing.

### Implementation Snippets

```python
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="Banking Copilot API")

class QueryRequest(BaseModel):
    question: str

class QueryResponse(BaseModel):
    answer: str
    answer_grounded: bool
    citations: list

@app.post("/query", response_model=QueryResponse)
async def query_endpoint(req: QueryRequest) -> QueryResponse:
    result = rag_query(req.question)
    return QueryResponse(
        answer=result["answer"],
        answer_grounded=result["answer_grounded"],
        citations=result["citations"],
    )

# Run: uvicorn main:app --reload
# Docs: http://localhost:8000/docs
```

### ELI5 Explanation

FastAPI is like a **restaurant-in-a-box**. You don't build walls and install a kitchen yourself (HTTP plumbing); they're pre-built. You write recipes (endpoint functions). The framework automatically prints a menu card for guests (Swagger docs at `/docs`) — no separate doc writing needed.

### Common Gotchas

Real build (Component 5): no surprises. `response_model=QueryResponse` with a nested `Citation` Pydantic model validated cleanly against the `rag_chain.py` return dict without extra glue code. `Exception` caught around `rag_query()` and mapped to a plain `{"error": ...}` JSON body — confirmed a raised `RuntimeError` never leaks a stack trace to the client (tested in `tests/test_api.py`). See Component 5 section below for the real Dockerfile/deploy notes.

---

## Containers & Docker

### What It Is

A **container** bundles an application, its code, all runtime dependencies (libraries, Python interpreter, system tools), and configuration into a single portable unit. It's lighter than a **VM** (which virtualizes a full OS kernel and hardware, weighs GB) — containers share the host OS kernel, are lightweight (MB), and start in milliseconds.

A **Dockerfile** is a text file with instructions to build a container image. A **container image** is a static, built snapshot (like a `.jar` file). A running **container** is a live instance of that image (like a running JVM process).

### Why It's Used Here

Cloud Run runs containers, not raw Python files. Your laptop has Python 3.11, numpy, google-cloud-firestore, etc. installed. Cloud Run's servers don't. A container brings those dependencies along — "this app works everywhere the container engine is installed" solves the "works on my machine" problem.

### Key Concepts

**Dockerfile Instructions:**
- **FROM** — base image (e.g., `python:3.11-slim`), provides the OS and language runtime.
- **COPY** — copy files from local machine into the image (e.g., `COPY src/ /app/src/`).
- **RUN** — execute a command during build (e.g., `RUN pip install -r requirements.txt`).
- **EXPOSE** — declare which port the app listens on (documentation; doesn't do networking).
- **CMD** — default command to run when container starts (e.g., `CMD ["python", "main.py"]`).

**Image vs. Container:**
- Image = class (static, reusable, stored in a registry).
- Container = instance (live, temporary, tied to a running process).

### Implementation Snippets

```dockerfile
# Conceptual Dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Build locally (not yet done; for reference):**
```bash
docker build -t banking-copilot:latest .
docker run -p 8000:8000 banking-copilot:latest
```

### ELI5 Explanation

A container is like an **IKEA-furniture-in-a-box shipment**. Instead of assuming the recipient owns a drill, screwdriver set, and wood stain, you ship everything inside the box — parts, tools, finishing supplies. The recipient doesn't need *their* tools; the box has everything. Cloud Run is the delivery company — you give it a box (container image), it runs whatever's inside (the furniture gets assembled).

### Common Gotchas

Real build (Component 5): no dependency surprises inside the container — the two-stage `uv sync --no-install-project` then `uv sync` pattern (deps layer cached separately from app code layer) meant editing `src/` didn't force a full dependency reinstall on rebuild. `uv` binary copied in via `COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/` rather than installed via pip — faster, no extra pip bootstrap layer. Biggest real gotcha wasn't Docker at all — it was Cloud Build IAM (see Cloud Run section below).

---

## Cloud Run

### What It Is

**Cloud Run** is a serverless container hosting service. You provide a container image; Cloud Run runs it on demand, exposes a public HTTPS URL, and manages scaling — no servers to manage, no instances to SSH into.

### Why It's Used Here

Fits the $0-spend goal:
- **Scales to zero.** No requests = no running containers = no charges. Idle cost is zero.
- **Always-Free tier:** 2M requests/month free, 360K CPU-seconds/month free. Enough for a non-production interview demo.
- **Container is portable.** Same image runs locally (Docker) or on Cloud Run (no code changes).

### Key Concepts

**Cold Start:** First request after idle spins up a fresh container instance (slower, ~1–5 sec). Subsequent requests within a few seconds reuse the warm instance (fast).

**Auto-Scaling:** Multiple instances under load; Cloud Run shuts down unused instances automatically.

**`gcloud run deploy`:** Deploys a service. With `--source=.`, Cloud Build auto-builds the image from local Dockerfile in the background.

**Service Account Attachment:** Cloud Run can run with a specific service account's identity (no key file involved — the service account is attached to the Cloud Run config). Code inside the container inherits that identity for GCP API calls.

### Implementation Snippets

**Deploy from local source (minimal example, not yet run):**
```bash
gcloud run deploy banking-copilot \
  --source=. \
  --platform=managed \
  --region=us-central1 \
  --allow-unauthenticated \
  --service-account=filings-rag-app@gcp-genai-banking.iam.gserviceaccount.com
```

This builds the image via Cloud Build, deploys to Cloud Run, attaches the service account, and returns a public HTTPS URL.

### ELI5 Explanation

Cloud Run is like **renting a food truck**. You don't own the truck or parking lot (no server management). You hand the company a recipe box (container image) and a phone number to call when customers arrive. The truck rolls in when it gets a call, cooks, and rolls away when the line empties. You pay per customer, not per day the truck sits idle.

### Common Gotchas

**Real gotcha — Cloud Build default service account missing IAM permissions on first deploy.** `gcloud run deploy --source=.` failed with `PERMISSION_DENIED... could not resolve source` fetching the uploaded source zip from the auto-created `run-sources-*` GCS bucket, attributed to the project's default compute service account (`PROJECT_NUMBER-compute@developer.gserviceaccount.com`). Root cause: `artifactregistry.googleapis.com`, `cloudbuild.googleapis.com`, and `run.googleapis.com` weren't enabled yet on this project (auto-prompted and enabled by the `deploy` command itself), and IAM role propagation for the newly-enabled Cloud Build service lagged behind. Fix: explicitly granted `roles/cloudbuild.builds.builder` to the compute default service account, then retried after a short wait — second retry succeeded. **Lesson:** on a freshly-provisioned project's first `--source=.` deploy, expect a possible IAM-propagation-related failure unrelated to app code; a retry after granting `cloudbuild.builds.builder` (or simply waiting a minute or two for propagation) resolves it. Not specific to this app — a one-time per-project setup gotcha.

Deploy succeeded on the retry with zero further issues. Full request-verification results (health/query/refusal, cold start, logs) are in the Component 5 real-build section below.

---

## Secret Manager

### What It Is

**Cloud Secret Manager** is a dedicated, version-controlled, access-controlled storage for sensitive values — API keys, credentials, database passwords, etc. Secrets are stored encrypted at rest, access is gated by IAM, and Cloud Run can inject a secret as an environment variable at container startup.

### Why It's Used Here

Secrets must **never** live in:
- Git repositories (even private ones, checked into history is permanent).
- Docker images (baked in, visible to anyone with image access).
- `.env` files shipped with code (portable as a container, visible to container inspectors).

Instead, store in Secret Manager, access via IAM, inject at runtime.

### Key Concepts

**Secret = named container;** `gemini-api-key` is a secret name.

**Version = a specific value over time;** version 1 was the original value, version 2 is a rotated value. Supports rotation without changing code — just add a new version and update Cloud Run's reference.

**IAM Access:** `roles/secretmanager.secretAccessor` grants read-only access to a specific secret for a specific identity (e.g., `filings-rag-app` service account). Even you (the user) can't read the value after creation without this role explicitly granted.

### Implementation Snippets

**Create a secret (one-step, as run this session):**
```bash
# Create secret with initial value in one command
echo -n "[REDACTED_KEY]" | gcloud secrets create gemini-api-key --data-file=- --project=gcp-genai-banking

# List versions
gcloud secrets versions list gemini-api-key

# Grant access to a service account
gcloud secrets add-iam-policy-binding gemini-api-key \
  --member=serviceAccount:filings-rag-app@gcp-genai-banking.iam.gserviceaccount.com \
  --role=roles/secretmanager.secretAccessor
```

**In application code (inside Cloud Run container, after injection):**
```python
import os

api_key = os.getenv("GEMINI_API_KEY")  # Cloud Run injects this from Secret Manager
```

**Cloud Run service deployment references the secret:**
```bash
gcloud run deploy banking-copilot \
  --set-env-vars=GEMINI_API_KEY=projects/PROJECT_ID/secrets/gemini-api-key/versions/latest \
  ...
```

### ELI5 Explanation

**Secret Manager is a bank vault; local `.env` is a sticky note on the door.**
- `.env` shipped with code: "House key location: 123 Main St." (anyone with the code has the key location).
- Secret Manager: key stored in a vault, only people pre-approved via ID can open it, and the vault logs every access.
- Cloud Run's secret injection: "Here's the vault access token for this service" — Cloud Run retrieves the actual value at startup, makes it available as an env var inside the container, no exposed value anywhere.

### Common Gotchas & Security Incidents

**Real incident this session — API key exposure in chat:**
During manual secret creation, the gemini-api-key value was pasted into an AI chat conversation as part of a shell command example, even though the intent was to keep it out of context by running commands manually/locally. **Once a credential appears in any conversation history (including AI chat), treat it as compromised** — recovery assumes active use of the credential elsewhere, and the history (even a deleted message) is not guaranteed to be unseen.

**Response and mitigation:**
1. Rotated the key in AI Studio (invalidated the old value at the source).
2. Added the new value as secret version 2 via `gcloud secrets versions add gemini-api-key ...`.
3. **Destroyed** the compromised version 1 via `gcloud secrets versions destroy 1 --secret=gemini-api-key` — destroy is irreversible and actually deletes the value data, vs. `disable` which only deactivates but keeps it recoverable. Destroy is the correct response to a leaked value.
4. **Lesson:** When sharing a command that embeds a secret value in visible text (even if the underlying execution is manual/local), redact the value in anything shown to another party, including an AI assistant. Example: show `echo -n "[REDACTED_KEY]" | gcloud secrets versions add ...` in the chat, run the actual value locally.

---

## Cloud Run Service Account Identity (vs. local key-file auth)

### What It Is

In Components 1–4 (local Python development), code explicitly loads a service account key file (`filings-rag-app-key.json`) to authenticate to GCP APIs. **Cloud Run's attached-identity model works differently:** the service account is attached to the Cloud Run service configuration itself. Code running inside automatically authenticates as that identity — **no key file involved anywhere.** The Cloud Run environment provides the credentials.

### Why It's Used Here (Deployment Context)

**Local auth (Components 1–4):** Key file is portable and explicit — the file is the credential. Risk: files get leaked (committed to git, exposed in a screenshot, copied to untrusted machines).

**Cloud Run auth:** Identity is bound to the service configuration, not a portable file. Access is revocable via IAM, independent of whether a key exists. Much harder to leak because there's no credential file to lose.

### Key Concepts

**Same service account, two contexts:**
- Local: code loads `filings-rag-app-key.json` explicitly via `credentials.from_service_account_file()`.
- Cloud Run: service account is attached to the Cloud Run service; code uses `google.auth.default()` which fetches credentials from the Cloud Run environment automatically.

**No code changes needed.** `google.auth.default()` is the pattern for both — it looks for credentials in the environment first (Cloud Run provides them there), then falls back to a local key file if available. Same code, different credential source per context.

**Roles are shared.** `filings-rag-app` already has `roles/datastore.user`, `roles/storage.objectViewer`, and `roles/secretmanager.secretAccessor` — these roles work whether the account authenticates via a key file (locally) or via Cloud Run's attached identity. No new service account needed.

### Implementation Snippets

**Local (components 1–4, using key file):**
```python
from google.auth import credentials
from google.cloud import firestore

creds = credentials.from_service_account_file("filings-rag-app-key.json")
db = firestore.Client(credentials=creds, project="gcp-genai-banking")
```

**Cloud Run (components 5+, using attached identity):**
```python
from google.cloud import firestore

# google.auth.default() checks Cloud Run environment first
db = firestore.Client(project="gcp-genai-banking")
# Credentials are fetched automatically from the Cloud Run metadata service
```

**Same code path works for both:**
```python
# This pattern works in both contexts
import google.auth

credentials, project = google.auth.default()
# On Cloud Run: credentials fetched from environment.
# Locally: credentials fetched from ~/.config/gcloud/ or a key file in the path.
```

**Deployment command attaches the service account:**
```bash
gcloud run deploy banking-copilot \
  --source=. \
  --service-account=filings-rag-app@gcp-genai-banking.iam.gserviceaccount.com \
  ...
```

### ELI5 Explanation

**Local key-file auth = carrying a physical badge.**
- Badge is your credential — it's portable, you can use it anywhere it's recognized.
- Risk: lose the badge (or a copy gets stolen), anyone can impersonate you.

**Cloud Run's attached identity = a building that recognizes you by which office you're in.**
- No badge needed — the building knows "this container is running in office 5, so it's the filings-rag-app identity."
- Access is tied to location/context, not a portable item.
- You change jobs (rotate credentials), the building automatically starts checking a different office's access list — no badge handoff needed.

### Common Gotchas

1. **`google.auth.default()` order matters for local dev.** It checks (in order): Google Cloud SDK credentials, then `GOOGLE_APPLICATION_CREDENTIALS` env var, then application default credentials. If multiple are set, first match wins. For local testing, explicitly set `GOOGLE_APPLICATION_CREDENTIALS=path/to/filings-rag-app-key.json` to avoid surprise auth failures.
2. **Cloud Run doesn't use key files.** Attempting to reference a key file path inside a container fails (the file isn't there). Always use `google.auth.default()` for Cloud Run code; it checks the environment automatically.
3. **Secret Manager access also uses attached identity.** When Cloud Run injects a secret as an env var, it's fetching the secret on behalf of the attached service account. That account must have `roles/secretmanager.secretAccessor` on that specific secret — no fallback if it doesn't.

---

## Component 5: FastAPI + Docker + Cloud Run — Real Build Notes

### What Was Built

`src/copilot/api.py` (FastAPI app, `/health` + `/query`), `app.py` (uvicorn entry point, loads `.env` for local runs), `Dockerfile`, `.dockerignore`. Deployed via `gcloud run deploy --source=.` (Cloud Build builds the image from the Dockerfile, no local Docker daemon needed).

### Real Working Dockerfile

```dockerfile
FROM python:3.11-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY src/ src/
COPY app.py ./

RUN uv sync --frozen --no-dev

RUN useradd -m appuser
USER appuser

EXPOSE 8080

CMD ["sh", "-c", ".venv/bin/uvicorn app:app --host 0.0.0.0 --port ${PORT:-8080}"]
```

Two-layer `uv sync` (deps-only first, then full) keeps the dependency-install layer cacheable across code-only rebuilds. `${PORT:-8080}` reads Cloud Run's injected `PORT` env var, falls back to 8080 for local `docker run`. `RUN useradd -m appuser` + `USER appuser` runs the container as non-root for security. CMD invokes `.venv/bin/uvicorn` directly (prebuilt at image build time) rather than `uv run uvicorn` — see gotcha below for why.

**Gotcha: `uv run <command>` at container CMD time re-resolves/downloads dependencies on every container start (not just build time)** — this is fine as root (fast, cached) but broke health checks when switching to a non-root user (permission friction accessing uv's cache, plus wasted startup time re-downloading packages like pygments). Fix: invoke the prebuilt virtual environment binary directly in CMD (`.venv/bin/uvicorn app:app ...`) instead of `uv run uvicorn ...` — this uses the environment already built during the Docker image build step, no re-resolution at runtime. General lesson: `uv run` is convenient for local dev where re-resolution is cheap/cached, but inside a container CMD, prefer calling the venv's binaries directly for faster, more reliable startup.

### Real Working Deploy Command

```bash
gcloud run deploy filings-rag-api \
  --source=. \
  --region=us-central1 \
  --service-account=filings-rag-app@gcp-genai-banking.iam.gserviceaccount.com \
  --set-secrets=GEMINI_API_KEY=gemini-api-key:latest \
  --allow-unauthenticated \
  --project=gcp-genai-banking
```

Deployed service: `https://filings-rag-api-27353588174.us-central1.run.app`

### What Actually Happened (vs. the pre-build conceptual session)

- **FastAPI:** no framework-specific surprises. `response_model` validation against the existing `rag_chain.py` dict shape worked with zero glue code.
- **Docker:** no dependency issues inside the container that hadn't shown up locally — the app has no OS-level dependencies beyond what `python:3.11-slim` + `uv sync` provide (no compiled-extension surprises from `pdfplumber` etc.).
- **Cloud Run / IAM (the one real gotcha):** first `--source=.` deploy failed with `PERMISSION_DENIED` fetching the uploaded source from the auto-created `run-sources-*` bucket — the project's default compute service account was missing `roles/cloudbuild.builds.builder`, compounded by IAM propagation lag right after `artifactregistry`/`cloudbuild`/`run` APIs were freshly auto-enabled. Granted the role, retried once, succeeded. One-time per-project setup issue, not app-related — see the Cloud Run section's gotchas above for full detail.
- **Cold start:** not separately load-tested this session (out of scope, per CLAUDE.md's explicit load-testing exclusion) — first real request (`/health` via curl) succeeded on the first try with no visible delay-related error; Cloud Run logs showed clean `Application startup complete` before it.
- **Logs:** checked via `gcloud run services logs read` — zero errors or warnings in the startup + first-request window.
- **Billing safeguard:** a $0/$1 zero-spend budget alert was configured this session on billing account `0147EC-94B896-30A818` ($1 threshold, email notification to default billing contacts) as the project's cost tripwire backstop — discussed early in the project but never actually set up until now.

### Live Verification (real deployed URL, not local)

- `GET /health` → `{"status":"ok"}`
- `POST /query` (in-scope, "What are ACME's main financial risks mentioned in the filing?") → real grounded answer, `answer_grounded: true`, 2 citations from `sample-10k`.
- `POST /query` (out-of-scope, "What is the population of Tokyo?") → refusal text, `answer_grounded: false`. Citations array is non-empty (nearest chunks still listed with high distance ~0.55) — expected per the Component 4 design: citations are attached programmatically regardless of relevance, `answer_grounded` is what disambiguates "used" vs. "searched but irrelevant."
- Full test suite: **18/18 passed** (3 new in `tests/test_api.py`, mocked `rag_query()`, no real API/Firestore calls).

### Security Note

Deployed with `--allow-unauthenticated` — the service URL is publicly callable by anyone with the link, no auth required. Acceptable for this demo (synthetic 10-K data only, no real sensitive information), but a deliberate tradeoff, not an oversight. Flagging here so it isn't a surprise later if this pattern gets reused for anything with real data.

---

## To Be Added (Phase 2+)

- **Firestore Indexing & Query Planning** — beyond basic composite vector index.
- **Gemini Function Calling**
- **RAG Evaluation & Grounding Checks** — formal metrics, labeled datasets, verifier agents.
- **LangGraph Verification Agents (Hallucination Mitigation)**
- **CI/CD & Cloud Build** — beyond manual `gcloud run deploy`.
- **Cost Monitoring & Alerts** — beyond the initial $0/$1 budget alert (real-time dashboards, per-service breakdowns).

---

**Last updated:** 2026-08-08 — through Phase 1 completion (Components 1-5 complete; FastAPI, Docker, Cloud Run deployed; budget alerts configured).
**Scope:** GCP_GEN_AI Banking Copilot, Phase 1 (Filings RAG MVP)
