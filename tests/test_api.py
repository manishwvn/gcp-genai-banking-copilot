from unittest.mock import patch

from fastapi.testclient import TestClient

from src.copilot.api import app

client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_query_returns_correct_shape():
    fake_result = {
        "answer": "ACME faces interest rate risk.",
        "citations": [{"source": "10k.pdf", "chunk_index": 0, "distance": 0.1}],
        "context_used": ["ACME faces interest rate risk."],
        "answer_grounded": True,
    }
    with patch("src.copilot.api.rag_query", return_value=fake_result):
        response = client.post("/query", json={"question": "What risks does ACME face?"})

    assert response.status_code == 200
    body = response.json()
    assert body["answer"] == "ACME faces interest rate risk."
    assert body["citations"] == [{"source": "10k.pdf", "chunk_index": 0, "distance": 0.1}]
    assert body["answer_grounded"] is True


def test_query_error_returns_clean_500():
    with patch("src.copilot.api.rag_query", side_effect=RuntimeError("boom")):
        response = client.post("/query", json={"question": "anything"})

    assert response.status_code == 500
    body = response.json()
    assert "error" in body
    assert "boom" not in body["error"]
