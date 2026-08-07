# Banking Document & Risk Intelligence Copilot

A grounded RAG chatbot over SEC filings and earnings-call transcripts, built end-to-end on Google Cloud and the Google AI Studio Gemini API — entirely within free-tier limits, by design. Retrieval is backed by Firestore's native vector search (no separate vector database), generation is strictly grounded with citations attached programmatically from retrieved source chunks (never trusted from model output), and the service is deployed as a public FastAPI API on Cloud Run. Built as a banking-domain portfolio project for technical interviews.

## Live Demo

Deployed service: **https://filings-rag-api-27353588174.us-central1.run.app**

```bash
curl https://filings-rag-api-27353588174.us-central1.run.app/health

curl -X POST https://filings-rag-api-27353588174.us-central1.run.app/query \
  -H "Content-Type: application/json" \
  -d '{"question": "What are the company'\''s main financial risks?"}'
```

This is a public demo endpoint running against synthetic filing data — no authentication required, no real or sensitive data involved.

## Architecture

```
SEC filings / transcripts (PDF)
  → ingest & chunk (sentence-boundary, overlap)
  → embed (Gemini embedding API, 768-dim)
  → Firestore native vector search (KNN, cosine)
  → retrieve top-k relevant chunks
  → grounded generation (Gemini, strict "answer only from context" prompt)
  → citations attached programmatically from chunk metadata
  → FastAPI (/query, /health)
  → Cloud Run (containerized, autoscaling)
```

Design principle: the model never reports its own citations. Citations are built in code from the actual retrieved chunks, so the response can't cite a source that wasn't really used.

## Tech Stack

- **Language / tooling:** Python 3.10+, [uv](https://docs.astral.sh/uv/) for dependency management
- **LLM & embeddings:** Google AI Studio Gemini API (`google-genai`) — free tier, separate from GCP billing
- **Vector store:** Firestore native vector search (KNN, cosine distance) — doubles as the app's document store, no dedicated vector DB
- **Web framework:** FastAPI, served by Uvicorn
- **Containerization:** Docker (non-root runtime user, Cloud Run `$PORT`-aware)
- **Hosting:** Cloud Run (serverless, scales to zero, capped `max-instances`)
- **Secrets:** Google Secret Manager, injected at runtime — no key files in the container
- **PDF parsing:** pdfplumber
- **Testing:** pytest, with mocked Firestore/Gemini calls (no live quota used in tests)

## Local Setup

```bash
git clone https://github.com/manishwvn/gcp-genai-banking-copilot.git
cd gcp-genai-banking-copilot
uv sync
```

Create a `.env` file with:

```
GOOGLE_APPLICATION_CREDENTIALS=/path/to/your-service-account-key.json
GEMINI_API_KEY=your-ai-studio-key
```

Run the API locally:

```bash
uv run uvicorn app:app --reload
```

Run the test suite:

```bash
uv run pytest
```

## Example API Usage

```bash
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"question": "What credit risks does the company disclose?"}'
```

Response shape:

```json
{
  "answer": "...",
  "citations": [
    { "source": "10k.pdf", "chunk_index": 0, "distance": 0.23 }
  ],
  "answer_grounded": true
}
```

`answer_grounded` distinguishes an answer actually generated from retrieved context (`true`) from a refusal issued because nothing relevant was found (`false`) — the refusal path always returns a fixed, non-hallucinated message.

## Project Status

**Phase 1 (complete):** Filings & disclosures RAG — ingestion, chunking, embedding, vector retrieval, grounded generation, FastAPI service, Cloud Run deployment.

**Phase 2 (planned):** Multi-skill agentic layer — KYC/document extraction, transaction fraud explainer, and a LangGraph supervisor agent routing across skills.

## License

MIT — see [LICENSE](LICENSE).
