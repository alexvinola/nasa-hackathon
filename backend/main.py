"""Entry point: `uv run uvicorn main:app --host 127.0.0.1 --port 8000` from backend/ (localhost only).

The rules engine (pulsar/) decides; biometrics, speech, vision and the director only measure, perceive and phrase.
"""

import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI

from biometrics import router as biometrics
from director import router as director
from pulsar.app import create_app
from senses import router as senses
from senses import warm_up


@asynccontextmanager
async def lifespan(app: FastAPI):
    threading.Thread(target=warm_up, daemon=True).start()  # have the model loaded before the first question
    yield


app = create_app(lifespan=lifespan, routers=(senses, biometrics, director))
