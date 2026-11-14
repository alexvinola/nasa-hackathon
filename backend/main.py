"""PULSAR backend. Run it with `uv run uvicorn main:app --host 127.0.0.1 --port 8000` from this folder."""

import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from director import router as director
from senses import router as senses
from senses import warm_up


@asynccontextmanager
async def lifespan(app: FastAPI):
    threading.Thread(target=warm_up, daemon=True).start()  # have the model loaded before the first question
    yield


app = FastAPI(title="PULSAR", lifespan=lifespan)
# Only pages served from this machine may call the backend.
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(senses)
app.include_router(director)
