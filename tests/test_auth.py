from src.copilot.firestore_client import get_db


def test_get_db_initializes_firestore_client():
    db = get_db()
    assert db is not None
