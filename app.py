"""Uvicorn entry point for the FastAPI web service."""
from dotenv import load_dotenv

load_dotenv()

from src.copilot.api import app  # noqa: E402
