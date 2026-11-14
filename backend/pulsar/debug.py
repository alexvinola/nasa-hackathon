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

MAX_EVENTS = 400  # the lines worth reading: verdict changes, Gemma, voice, errors, one-off requests
MAX_NOISY = 100  # requests the HUD repeats every second or two, kept apart so they cannot push the rest out
MAX_TEXT = 240  # an event is one line: a model's answer is cut to this

router = APIRouter(tags=["debug"])

_events: deque[dict[str, Any]] = deque(maxlen=MAX_EVENTS)
_noisy: deque[dict[str, Any]] = deque(maxlen=MAX_NOISY)
_newest = 0  # id of the last event recorded by this process; a restarted backend starts again from 0
_ids = itertools.count(1)
_lock = threading.Lock()  # endpoints run in a thread pool


def record(kind: str, text: str, noisy: bool = False, **data: Any) -> None:
    """Add one event. `kind` groups them in the panel: http, engine, gemma, voice, error."""
    global _newest
    text = " ".join(str(text).split())
    if len(text) > MAX_TEXT:
        text = text[: MAX_TEXT - 1] + "…"
    with _lock:
        _newest = next(_ids)
        (_noisy if noisy else _events).append({"id": _newest, "at": time.time(), "kind": kind, "text": text, "noisy": noisy, **data})


def events_after(after: int) -> list[dict[str, Any]]:
    with _lock:
        return sorted((event for event in (*_events, *_noisy) if event["id"] > after), key=lambda event: event["id"])


def clear() -> None:
    with _lock:
        _events.clear()
        _noisy.clear()


@router.get("/debug/events", summary="What the backend did lately, for the HUD's log panel")
def events(after: int = 0) -> dict[str, Any]:
    # `last` is this process's newest id, not an echo of `after`: after a restart it is smaller, and the panel starts over.
    return {"events": events_after(after), "last": _newest}
