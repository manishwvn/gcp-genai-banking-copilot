"""PDF extraction, chunking, and Firestore ingestion for filings/transcripts (Phase 1 RAG pipeline)."""
import re
from datetime import datetime, timezone
from typing import List

import pdfplumber

CHARS_PER_TOKEN = 4


def read_pdf_text(filepath: str) -> str:
    """Extracts full text from a PDF, concatenating all pages."""
    pages = []
    with pdfplumber.open(filepath) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                pages.append(text)
    return "\n\n".join(pages)


def chunk_text(text: str, chunk_size: int = 800, overlap: int = 100) -> List[str]:
    """Splits text into ~chunk_size-token chunks along sentence boundaries, with overlap between chunks."""
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    sentences = [s.strip() for s in sentences if s.strip()]

    chunk_size_chars = chunk_size * CHARS_PER_TOKEN
    overlap_chars = overlap * CHARS_PER_TOKEN

    chunks = []
    current: List[str] = []
    current_len = 0

    for sentence in sentences:
        current.append(sentence)
        current_len += len(sentence) + 1

        if current_len >= chunk_size_chars:
            chunks.append(" ".join(current))

            overlap_sentences = []
            overlap_len = 0
            for s in reversed(current):
                overlap_len += len(s) + 1
                overlap_sentences.insert(0, s)
                if overlap_len >= overlap_chars:
                    break
            current = overlap_sentences
            current_len = sum(len(s) + 1 for s in current)

    if current:
        chunks.append(" ".join(current))

    return chunks


def create_firestore_chunks(filepath: str, source_name: str, db) -> int:
    """Reads a PDF, chunks its text, and writes each chunk as a document in the filings_chunks collection.

    Returns the number of chunks written.
    """
    text = read_pdf_text(filepath)
    chunks = chunk_text(text)

    collection = db.collection("filings_chunks")
    for index, chunk in enumerate(chunks):
        collection.add({
            "text": chunk,
            "source": source_name,
            "source_url": f"local://{filepath}",
            "page_number": 0,
            "chunk_index": index,
            "created_at": datetime.now(timezone.utc),
        })

    return len(chunks)
