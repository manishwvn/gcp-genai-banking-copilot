# learnings.md — GCP_GEN_AI Service & Concept Deep-Dives

This document captures what was learned about each GCP service and concept used in the Banking Copilot project, with implementation snippets, ELI5 explanations, and gotchas. Updated after each phase/session.

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
- **Phase 2:** KYC extraction results, flagged transactions, and verification audit logs.
- **Vector search:** Query documents by semantic similarity — the core of RAG retrieval.
- **Always-Free tier:** 1 GiB storage, 50K reads / 20K writes / 20K deletes per day — plenty for an MVP.

### Key Concepts

**Document:** A single record (like a row in SQL). Contains fields (key-value pairs). Docs are versioned and timestamped.

**Collection:** A grouping of documents (like a table). Can be top-level or nested under another document (subcollections).

**Vector field:** A field that stores a dense embedding (list of floats). Firestore indexes these for KNN (K-nearest neighbor) search. Dimension can be up to 2048 (common: 768 for many embedding models).

**Vector search:** Query: "Find docs similar to this vector." Firestore returns the K closest neighbors by distance (cosine, Euclidean, dot product).

**Real-time listeners:** You can subscribe to live updates — if a document changes, your app is notified immediately.

### Implementation Snippets

We'll do these in Claude Code Phase 1, but here's the concept:

**Initialize Firestore (Python):**
```python
from google.cloud import firestore

db = firestore.Client(project="gcp-genai-banking")
```

**Add a document with an embedding:**
```python
db.collection("filings").document("10k-2024").set({
    "title": "ACME Corp 10-K 2024",
    "source": "SEC EDGAR",
    "embedding": firestore.Vector([0.12, 0.34, -0.56, ...]),  # 768-dim vector
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
- **Gemini 2.5 Flash:** ~15 requests per minute, ~1,500 requests per day.
- **Gemini 3.1 Flash-Lite:** Similar, slightly higher RPM.
- **Embedding models (text-embedding-005):** Free tier, but check docs for current limits (usually generous).
- **Image generation (Gemini 2.5 Flash Image):** 500 requests/day.
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
```python
response = genai.embed_content(
    model="models/text-embedding-005",
    content="SEC filing summary text here..."
)
embedding = response['embedding']  # List of 768 floats
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
# Firestore chunk document
collection.add({
    "text": chunk,
    "source": source_name,
    "source_url": f"local://{filepath}",
    "page_number": 0,
    "chunk_index": index,
    "created_at": datetime.now(timezone.utc),
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

## To Be Added

- **IAM Deep-dive (service accounts, key management)**
- **Firestore Indexing & Query Planning**
- **Cloud Run Deployment, Secrets Injection, Logging**
- **LangChain & LangGraph Patterns**
- **Gemini Function Calling**
- **Vector Embeddings: Concepts & Dimensions**
- **RAG Evaluation & Grounding Checks**
- **LangGraph Verification Agents (Hallucination Mitigation)**
- **CI/CD & Cloud Build**
- **Cost Monitoring & Alerts**

---

**Last updated:** 2026-08-05 (Component 2 completion: embedding generation, vector indexing, free-tier billing architecture)
**Scope:** GCP_GEN_AI Banking Copilot, Phase 1 (Filings RAG MVP)
