"""Entry point: `uv run uvicorn main:app` from backend/ (localhost only)."""

import threading
from contextlib import asynccontextmanager

from biometrics import router as biometrics
from director import router as director
from pulsar.app import create_app
from senses import router as senses
from senses import warm_up

app = create_app()
app.include_router(senses)
app.include_router(biometrics)
app.include_router(director)


@asynccontextmanager
async def lifespan(_app):
    threading.Thread(target=warm_up, daemon=True).start()  # have the model loaded before the first question
    yield


app.router.lifespan_context = lifespan
