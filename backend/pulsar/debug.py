"""What the backend is doing, for the HUD's log panel: the last events, kept in memory only.

- GET /debug/events?after=<id>  events newer than `after`, oldest first, and the id to ask from next time

Every request is recorded by the middleware in `pulsar.app` (path, status, milliseconds); the endpoints add what
the access line cannot say: the engine's verdict, how long Gemma took and what it answered, what Whisper heard.
Nothing is written to disk and no image or audio is ever put in an event. Localhost only, like the rest of the API.
"""

import itertools
import threading
import time
from collections import deque
from typing import Any

from fastapi import APIRouter

MAX_EVENTS = 400  # about the last few minutes of a live HUD
MAX_TEXT = 240  # an event is one line: a model's answer is cut to this

router = APIRouter(tags=["debug"])

_events: deque[dict[str, Any]] = deque(maxlen=MAX_EVENTS)
_ids = itertools.count(1)
_lock = threading.Lock()  # endpoints run in a thread pool


def record(kind: str, text: str, **data: Any) -> None:
    """Add one event. `kind` groups them in the panel: http, engine, gemma, voice, error."""
    text = " ".join(str(text).split())
    if len(text) > MAX_TEXT:
        text = text[: MAX_TEXT - 1] + "…"
    with _lock:
        _events.append({"id": next(_ids), "at": time.time(), "kind": kind, "text": text, **data})


def events_after(after: int) -> list[dict[str, Any]]:
    with _lock:
        return [event for event in _events if event["id"] > after]


def clear() -> None:
    with _lock:
        _events.clear()


@router.get("/debug/events", summary="What the backend did lately, for the HUD's log panel")
def events(after: int = 0) -> dict[str, Any]:
    found = events_after(after)
    return {"events": found, "last": found[-1]["id"] if found else after}
