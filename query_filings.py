"""CLI entry point for querying the filings RAG chain."""
import sys

from dotenv import load_dotenv

from src.copilot.rag_chain import rag_query

load_dotenv()


def main():
    if len(sys.argv) > 1:
        question = " ".join(sys.argv[1:])
    else:
        question = input("Question: ")

    result = rag_query(question)

    print(f"\nAnswer (grounded={result['answer_grounded']}):")
    print(result["answer"])

    print("\nCitations:")
    if not result["citations"]:
        print("  (none)")
    for c in result["citations"]:
        print(f"  - source={c['source']} chunk_index={c['chunk_index']} distance={c['distance']}")


if __name__ == "__main__":
    main()
