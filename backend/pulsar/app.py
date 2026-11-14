"""FastAPI application factory. `main.py` exposes the instance as `app`."""

import time
from collections.abc import Iterable

from fastapi import APIRouter, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from pulsar import debug, settings
from pulsar.rules import build_engine
from pulsar.rules.api import router as rules_router
from pulsar.vision.api import router as vision_router
from pulsar.voice.api import router as voice_router


QUIET_PATHS = {"/debug/events", "/health"}
NOISY_PATHS = {"/biometrics", "/rules/evaluate"}  # sent by the HUD every second or two


def create_app(lifespan=None, routers: Iterable[APIRouter] = ()) -> FastAPI:
    app = FastAPI(
        lifespan=lifespan,
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
    app.include_router(voice_router)
    app.include_router(vision_router)
    app.include_router(debug.router)
    for router in routers:
        app.include_router(router)

    @app.middleware("http")
    async def log_request(request: Request, call_next):
        """One line per request in the HUD's log; the log's own polling and CORS preflights would only bury the rest."""
        path = request.url.path
        if request.method == "OPTIONS" or path in QUIET_PATHS:
            return await call_next(request)
        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception as error:
            # The class only: an exception's text can quote the bytes of a request body.
            debug.record("error", f"{request.method} {path} failed: {type(error).__name__}", path=path)
            raise
        ms = round((time.perf_counter() - started) * 1000)
        failed = response.status_code >= 400
        debug.record("error" if failed else "http", f"{request.method} {path} {response.status_code} · {ms} ms",
                     noisy=path in NOISY_PATHS and not failed, path=path, status=response.status_code, ms=ms)
        return response

    @app.get("/health", tags=["health"], summary="Liveness probe for start_synapse")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app
