"""Gemini embedding generation (Phase 1 RAG pipeline)."""
import math
import os
import time

from google import genai
from google.genai import types

EMBEDDING_MODEL = "gemini-embedding-001"
EMBEDDING_DIM = 768
MAX_RETRIES = 3
BACKOFF_BASE_SECONDS = 2

_client = None


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError(
                "GEMINI_API_KEY not set. Add it to .env (get a free key at aistudio.google.com)."
            )
        _client = genai.Client(api_key=api_key)
    return _client


def embed_text(text: str) -> list:
    """Generates a 768-dim embedding vector for text using the Gemini embeddings API.

    Retries on transient/rate-limit errors with exponential backoff before failing loudly.
    """
    client = _get_client()

    last_error = None
    for attempt in range(MAX_RETRIES):
        try:
            response = client.models.embed_content(
                model=EMBEDDING_MODEL,
                contents=text,
                config=types.EmbedContentConfig(output_dimensionality=EMBEDDING_DIM),
            )
            values = response.embeddings[0].values
            # gemini-embedding-001 doesn't auto-normalize when output_dimensionality < 3072 — normalize manually.
            norm = math.sqrt(sum(v * v for v in values))
            return [v / norm for v in values]
        except Exception as e:
            last_error = e
            if attempt < MAX_RETRIES - 1:
                time.sleep(BACKOFF_BASE_SECONDS * (2 ** attempt))

    raise RuntimeError(f"embed_text failed after {MAX_RETRIES} attempts: {last_error}") from last_error
