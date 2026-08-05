"""Firestore client initialization helper."""
from dotenv import load_dotenv
from google.cloud import firestore

load_dotenv()

_db = None


def get_db() -> firestore.Client:
    """Returns a cached Firestore client instance, creating it on first call."""
    global _db
    if _db is None:
        _db = firestore.Client()
    return _db
