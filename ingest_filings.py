"""Ingests all filings in data/filings/ into Firestore as chunks."""
from pathlib import Path

from dotenv import load_dotenv

from src.copilot.document_ingestion import create_firestore_chunks
from src.copilot.firestore_client import get_db

load_dotenv()

FILINGS_DIR = Path("data/filings")


def main():
    db = get_db()

    pdf_files = sorted(FILINGS_DIR.glob("*.pdf"))
    if not pdf_files:
        print(f"No PDF files found in {FILINGS_DIR}")
        return

    for pdf_path in pdf_files:
        source_name = pdf_path.stem
        num_chunks = create_firestore_chunks(str(pdf_path), source_name, db)
        print(f"Ingested {pdf_path.name}: {num_chunks} chunks")

    total = sum(1 for _ in db.collection("filings_chunks").stream())
    print(f"Total documents in filings_chunks collection: {total}")


if __name__ == "__main__":
    main()
