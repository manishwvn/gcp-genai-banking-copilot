"""Grounded generation over retrieved filings chunks (Phase 1 RAG pipeline)."""
import os

from google import genai

from src.copilot.retrieval import retrieve_relevant_chunks

GENERATION_MODEL = "gemini-flash-latest"

REFUSAL_TEXT = (
    "I don't have enough information in the available documents to answer this."
)

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


def _build_prompt(question: str, retrieved_chunks: list) -> str:
    context_block = "\n\n".join(
        f"[{i}] {chunk['text']}" for i, chunk in enumerate(retrieved_chunks, start=1)
    )
    return (
        "Answer ONLY using the provided context. If the answer is not present in "
        "the context, respond exactly: 'I don't have enough information in the "
        "available documents to answer this.' Do not use outside knowledge. When "
        "you state a fact, reference which context number it came from, like [1].\n\n"
        f"Context:\n{context_block}\n\n"
        f"Question: {question}"
    )


def generate_grounded_answer(question: str, retrieved_chunks: list) -> dict:
    """Generates an answer constrained to retrieved_chunks; citations attached programmatically."""
    citations = [
        {
            "source": chunk["source"],
            "chunk_index": chunk["chunk_index"],
            "distance": chunk["distance"],
        }
        for chunk in retrieved_chunks
    ]
    context_used = [chunk["text"] for chunk in retrieved_chunks]

    if not retrieved_chunks:
        return {
            "answer": REFUSAL_TEXT,
            "citations": [],
            "context_used": [],
            "answer_grounded": False,
        }

    client = _get_client()
    prompt = _build_prompt(question, retrieved_chunks)
    response = client.models.generate_content(model=GENERATION_MODEL, contents=prompt)
    answer = response.text.strip()

    # False when the model issued the refusal despite chunks being retrieved —
    # distinguishes "answered from context" from "searched but found nothing usable".
    answer_grounded = answer != REFUSAL_TEXT

    return {
        "answer": answer,
        "citations": citations,
        "context_used": context_used,
        "answer_grounded": answer_grounded,
    }


def rag_query(question: str, top_k: int = 4) -> dict:
    """End-to-end: retrieve relevant chunks, then generate a grounded answer."""
    retrieved_chunks = retrieve_relevant_chunks(question, top_k=top_k)
    return generate_grounded_answer(question, retrieved_chunks)
