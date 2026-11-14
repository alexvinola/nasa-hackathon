"""FastAPI application factory. `main.py` exposes the instance as `app`."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from pulsar import settings
from pulsar.rules import build_engine
from pulsar.rules.api import router as rules_router


def create_app() -> FastAPI:
    app = FastAPI(
        title="PULSAR backend",
        description=(
            "Offline health companion for astronauts. The rules engine decides; "
            "the voice pipeline (not implemented yet) only phrases its verdict. Not a medical device."
        ),
        version="0.1.0",
    )
    # Built eagerly so a rules file that does not trace back to shared/ fails at startup, not mid-demo.
    app.state.rules_engine = build_engine()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )
    app.include_router(rules_router)

    @app.get("/health", tags=["health"], summary="Liveness probe for start_synapse")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app
