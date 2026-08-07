"""Semantic retrieval over filings_chunks (Phase 1 RAG pipeline)."""
from google.cloud.firestore_v1.base_vector_query import DistanceMeasure
from google.cloud.firestore_v1.vector import Vector

from src.copilot.embeddings import embed_text
from src.copilot.firestore_client import get_db


def retrieve_relevant_chunks(question: str, top_k: int = 4) -> list:
    """Embeds the question and returns the top_k nearest filings_chunks by cosine distance.

    Each result: {text, source, chunk_index, distance}.
    """
    query_vector = Vector(embed_text(question))

    db = get_db()
    collection = db.collection("filings_chunks")
    vector_query = collection.find_nearest(
        vector_field="embedding",
        query_vector=query_vector,
        distance_measure=DistanceMeasure.COSINE,
        limit=top_k,
        distance_result_field="distance",
    )

    results = []
    for doc in vector_query.stream():
        data = doc.to_dict()
        results.append(
            {
                "text": data.get("text", ""),
                "source": data.get("source", "?"),
                "chunk_index": data.get("chunk_index"),
                "distance": data.get("distance"),
            }
        )
    return results
