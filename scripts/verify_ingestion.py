"""One-off verification script: inspects filings_chunks collection for data correctness."""
from src.copilot.firestore_client import get_db

MAX_DOC_BYTES = 1_000_000

db = get_db()
docs = list(db.collection("filings_chunks").stream())

print(f"Total documents: {len(docs)}")

by_source = {}
oversized = []
empty = []

for doc in docs:
    d = doc.to_dict()
    source = d.get("source", "?")
    text = d.get("text", "")
    chunk_index = d.get("chunk_index")
    page_number = d.get("page_number")

    print(f"source={source} chunk_index={chunk_index} page_number={page_number} "
          f"text_len={len(text)} preview={text[:100]!r}")

    by_source.setdefault(source, []).append(chunk_index)

    if len(text.encode("utf-8")) > MAX_DOC_BYTES:
        oversized.append((source, chunk_index))
    if len(text.strip()) < 20:
        empty.append((source, chunk_index))

print("\n--- Checks ---")
print("Oversized (>1MB) chunks:", oversized if oversized else "none")
print("Empty/near-empty chunks:", empty if empty else "none")

for source, indices in by_source.items():
    expected = list(range(len(indices)))
    actual_sorted = sorted(indices)
    ok = actual_sorted == expected
    print(f"source={source}: chunk_index sequence {actual_sorted} "
          f"{'OK (sequential, no dupes)' if ok else 'MISMATCH'}")
