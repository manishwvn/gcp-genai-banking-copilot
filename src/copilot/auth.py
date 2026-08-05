"""Loads GCP service account credentials and verifies Firestore reachability."""
import os

from dotenv import load_dotenv
from google.cloud import firestore

load_dotenv()


def get_credentials_path() -> str:
    path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if not path:
        raise RuntimeError("GOOGLE_APPLICATION_CREDENTIALS not set in .env")
    return path


def verify_firestore_auth() -> firestore.Client:
    """Instantiates a Firestore client using GOOGLE_APPLICATION_CREDENTIALS and returns it."""
    get_credentials_path()
    return firestore.Client()
