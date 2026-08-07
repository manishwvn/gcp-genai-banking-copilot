from unittest.mock import MagicMock, patch

from src.copilot import retrieval


def _fake_doc(text, source, chunk_index, distance):
    doc = MagicMock()
    doc.to_dict.return_value = {
        "text": text,
        "source": source,
        "chunk_index": chunk_index,
        "distance": distance,
    }
    return doc


def test_retrieve_relevant_chunks_returns_correct_shape():
    fake_docs = [_fake_doc("chunk one", "10k.pdf", 0, 0.1), _fake_doc("chunk two", "10k.pdf", 1, 0.2)]

    mock_vector_query = MagicMock()
    mock_vector_query.stream.return_value = fake_docs

    mock_collection = MagicMock()
    mock_collection.find_nearest.return_value = mock_vector_query

    mock_db = MagicMock()
    mock_db.collection.return_value = mock_collection

    with patch("src.copilot.retrieval.embed_text", return_value=[0.1] * 768):
        with patch("src.copilot.retrieval.get_db", return_value=mock_db):
            results = retrieval.retrieve_relevant_chunks("some question", top_k=2)

    assert len(results) == 2
    assert results[0] == {
        "text": "chunk one",
        "source": "10k.pdf",
        "chunk_index": 0,
        "distance": 0.1,
    }
    mock_collection.find_nearest.assert_called_once()
    _, kwargs = mock_collection.find_nearest.call_args
    assert kwargs["limit"] == 2


def test_retrieve_relevant_chunks_empty_result():
    mock_vector_query = MagicMock()
    mock_vector_query.stream.return_value = []

    mock_collection = MagicMock()
    mock_collection.find_nearest.return_value = mock_vector_query

    mock_db = MagicMock()
    mock_db.collection.return_value = mock_collection

    with patch("src.copilot.retrieval.embed_text", return_value=[0.1] * 768):
        with patch("src.copilot.retrieval.get_db", return_value=mock_db):
            results = retrieval.retrieve_relevant_chunks("unrelated question")

    assert results == []
