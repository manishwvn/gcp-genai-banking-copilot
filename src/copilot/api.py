"""FastAPI web service for the filings RAG chatbot."""
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from src.copilot.rag_chain import rag_query

app = FastAPI(title="Filings RAG Copilot")


class QueryRequest(BaseModel):
    question: str


class Citation(BaseModel):
    source: str
    chunk_index: int
    distance: float


class QueryResponse(BaseModel):
    answer: str
    citations: list[Citation]
    answer_grounded: bool


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/query", response_model=QueryResponse)
def query(request: QueryRequest):
    try:
        result = rag_query(request.question)
    except Exception:
        return JSONResponse(status_code=500, content={"error": "Failed to process query."})

    return QueryResponse(
        answer=result["answer"],
        citations=result["citations"],
        answer_grounded=result["answer_grounded"],
    )
