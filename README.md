# GCP GenAI Banking Copilot

Filings & disclosures RAG copilot for banking documents, built on GCP + Gemini, running entirely within Always-Free tiers.

## Prerequisites

- Python 3.10+
- [uv](https://docs.astral.sh/uv/) installed
- GCP project with Firestore + Cloud Storage enabled, service account key with `datastore.user` and `storage.objectViewer` roles

## Local Setup

```bash
git clone <repo-url>
cd GCP_GEN_AI
uv venv
source .venv/bin/activate
uv sync
```

Set the following in `.env`:

```
GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account-key.json
GEMINI_API_KEY=your-ai-studio-key
```

Verify setup:

```bash
python main.py
```

## Running Tests

```bash
pytest
```

## Project Structure

```
src/copilot/
  auth.py              # loads credentials, verifies Firestore auth
  firestore_client.py  # Firestore client init + get_db() helper
  embeddings.py        # Gemini embedding generation (stub, Phase 1 RAG)
tests/
  test_auth.py         # Firestore client init test
main.py                 # entrypoint smoke test
```
