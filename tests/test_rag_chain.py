from unittest.mock import MagicMock, patch

import pytest

from src.copilot import rag_chain


@pytest.fixture(autouse=True)
def reset_client():
    rag_chain._client = None
    yield
    rag_chain._client = None


@pytest.fixture
def sample_chunks():
    return [
        {"text": "ACME faces interest rate risk.", "source": "10k.pdf", "chunk_index": 0, "distance": 0.1},
        {"text": "ACME faces currency risk.", "source": "10k.pdf", "chunk_index": 1, "distance": 0.2},
    ]


def _fake_gemini_response(text):
    response = MagicMock()
    response.text = text
    return response


def test_generate_grounded_answer_attaches_citations_from_chunks(monkeypatch, sample_chunks):
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key")
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = _fake_gemini_response(
        "ACME faces interest rate risk [1] and currency risk [2]."
    )

    with patch("src.copilot.rag_chain.genai.Client", return_value=mock_client):
        result = rag_chain.generate_grounded_answer("What risks does ACME face?", sample_chunks)

    assert result["citations"] == [
        {"source": "10k.pdf", "chunk_index": 0, "distance": 0.1},
        {"source": "10k.pdf", "chunk_index": 1, "distance": 0.2},
    ]
    assert result["context_used"] == [
        "ACME faces interest rate risk.",
        "ACME faces currency risk.",
    ]
    assert "[1]" in result["answer"]
    assert result["answer_grounded"] is True


def test_generate_grounded_answer_citations_independent_of_model_text(monkeypatch, sample_chunks):
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key")
    mock_client = MagicMock()
    # model text mentions no citation markers at all
    mock_client.models.generate_content.return_value = _fake_gemini_response("ACME has risks.")

    with patch("src.copilot.rag_chain.genai.Client", return_value=mock_client):
        result = rag_chain.generate_grounded_answer("What risks does ACME face?", sample_chunks)

    # citations still attached programmatically regardless of model output
    assert len(result["citations"]) == 2


def test_generate_grounded_answer_refuses_on_empty_chunks():
    result = rag_chain.generate_grounded_answer("What is the population of Tokyo?", [])

    assert result["answer"] == rag_chain.REFUSAL_TEXT
    assert result["citations"] == []
    assert result["context_used"] == []
    assert result["answer_grounded"] is False


def test_generate_grounded_answer_flags_ungrounded_when_model_refuses_with_chunks(monkeypatch, sample_chunks):
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key")
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = _fake_gemini_response(rag_chain.REFUSAL_TEXT)

    with patch("src.copilot.rag_chain.genai.Client", return_value=mock_client):
        result = rag_chain.generate_grounded_answer("unrelated question", sample_chunks)

    assert result["answer_grounded"] is False
    assert len(result["citations"]) == 2  # chunks were retrieved, just not used


def test_rag_query_chains_retrieval_and_generation(sample_chunks):
    with patch("src.copilot.rag_chain.retrieve_relevant_chunks", return_value=sample_chunks) as mock_retrieve:
        with patch(
            "src.copilot.rag_chain.generate_grounded_answer",
            return_value={"answer": "ok", "citations": [], "context_used": []},
        ) as mock_generate:
            result = rag_chain.rag_query("What risks does ACME face?", top_k=2)

    mock_retrieve.assert_called_once_with("What risks does ACME face?", top_k=2)
    mock_generate.assert_called_once_with("What risks does ACME face?", sample_chunks)
    assert result == {"answer": "ok", "citations": [], "context_used": []}
