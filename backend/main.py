"""PULSAR backend. Run it with `uv run uvicorn main:app --host 127.0.0.1 --port 8000` from this folder."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from senses import router as senses

app = FastAPI(title="PULSAR")
# Only pages served from this machine may call the backend.
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(senses)
