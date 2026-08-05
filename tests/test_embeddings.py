from unittest.mock import MagicMock, patch

import pytest

from src.copilot import embeddings


def _fake_response(dim=768):
    embedding = MagicMock()
    embedding.values = [0.1] * dim
    response = MagicMock()
    response.embeddings = [embedding]
    return response


@pytest.fixture(autouse=True)
def reset_client():
    embeddings._client = None
    yield
    embeddings._client = None


def test_embed_text_returns_correct_length(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key")
    mock_client = MagicMock()
    mock_client.models.embed_content.return_value = _fake_response()

    with patch("src.copilot.embeddings.genai.Client", return_value=mock_client):
        result = embeddings.embed_text("some filing text")

    assert isinstance(result, list)
    assert len(result) == embeddings.EMBEDDING_DIM


def test_embed_text_retries_then_succeeds(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key")
    mock_client = MagicMock()
    mock_client.models.embed_content.side_effect = [
        Exception("429 rate limit"),
        _fake_response(),
    ]

    with patch("src.copilot.embeddings.genai.Client", return_value=mock_client):
        with patch("src.copilot.embeddings.time.sleep"):
            result = embeddings.embed_text("some filing text")

    assert len(result) == embeddings.EMBEDDING_DIM
    assert mock_client.models.embed_content.call_count == 2


def test_embed_text_raises_after_max_retries(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key")
    mock_client = MagicMock()
    mock_client.models.embed_content.side_effect = Exception("persistent failure")

    with patch("src.copilot.embeddings.genai.Client", return_value=mock_client):
        with patch("src.copilot.embeddings.time.sleep"):
            with pytest.raises(RuntimeError, match="failed after"):
                embeddings.embed_text("some filing text")

    assert mock_client.models.embed_content.call_count == embeddings.MAX_RETRIES


def test_embed_text_missing_api_key_raises(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    with pytest.raises(RuntimeError, match="GEMINI_API_KEY"):
        embeddings.embed_text("some filing text")
