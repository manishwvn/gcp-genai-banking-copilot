from src.copilot.document_ingestion import chunk_text


def test_chunk_text_respects_sentence_boundaries():
    text = "First sentence here. Second sentence here. Third sentence here."
    chunks = chunk_text(text, chunk_size=5, overlap=2)

    assert len(chunks) > 0
    for chunk in chunks:
        assert chunk.strip().endswith((".", "!", "?"))


def test_chunk_text_produces_overlap_between_consecutive_chunks():
    text = " ".join(f"Sentence number {i} of the document." for i in range(50))
    chunks = chunk_text(text, chunk_size=50, overlap=20)

    assert len(chunks) > 1
    for prev, nxt in zip(chunks, chunks[1:]):
        prev_end = prev.split()[-5:]
        assert any(word in nxt for word in prev_end)


def test_chunk_text_single_short_text_returns_one_chunk():
    text = "Just one short sentence."
    chunks = chunk_text(text, chunk_size=800, overlap=100)

    assert chunks == ["Just one short sentence."]
