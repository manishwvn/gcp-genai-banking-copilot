"""Embeds all filings_chunks documents that don't yet have an embedding, in place."""
import time

from dotenv import load_dotenv
from google.cloud.firestore_v1.vector import Vector

from src.copilot.embeddings import embed_text
from src.copilot.firestore_client import get_db

load_dotenv()

DELAY_SECONDS = 5


def main():
    db = get_db()
    collection = db.collection("filings_chunks")

    docs = list(collection.stream())
    to_embed = [doc for doc in docs if "embedding" not in doc.to_dict()]
    skipped = len(docs) - len(to_embed)

    total = len(to_embed)
    for i, doc in enumerate(to_embed, start=1):
        data = doc.to_dict()
        source = data.get("source", "?")
        text = data.get("text", "")

        vector_values = embed_text(text)
        doc.reference.update({"embedding": Vector(vector_values)})

        print(f"Embedded chunk {i}/{total} (source: {source})...")

        if i < total:
            time.sleep(DELAY_SECONDS)

    print(f"\nTotal embedded: {total}")
    print(f"Total skipped (already had embeddings): {skipped}")


if __name__ == "__main__":
    main()
