"""Entry point: `uv run uvicorn main:app` from backend/ (localhost only)."""

from pulsar.app import create_app

app = create_app()
