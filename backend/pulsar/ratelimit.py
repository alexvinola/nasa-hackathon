"""Rate limits per client, in memory: a runaway page or a visitor cannot keep Gemma, Whisper or Piper busy.

Each request belongs to one group by its path and each client (its address) has a token bucket per group: a burst
it may spend at once and a steady refill. Over the limit the answer is 429 with `Retry-After`, before any model is
called. The limits sit well above what one HUD sends (it evaluates every 2 s, posts readings every second and asks
Gemma a few times a minute), so a normal session never meets them.

- PULSAR_RATE_LIMITS  `off` disables it; otherwise `group=per_minute` pairs, e.g. `model=30,speech=20,other=600`.

All three figures are team assumptions, sized from the HUD's own traffic, not from a measured capacity.
"""

import math
import os
import threading
import time
from dataclasses import dataclass

# Requests a minute for each group; the burst is a quarter of it (at least 5).
DEFAULT_LIMITS = {
    "model": 60,  # anything that calls Gemma: about 15 a minute from one HUD
    "speech": 40,  # Whisper and Piper
    "other": 900,  # readings, rule evaluations, listings: about 90 a minute from one HUD
}
MODEL_PATHS = ("/pulsar/act", "/voice/advise", "/vision/describe", "/vision/verify")
SPEECH_PATHS = ("/stt", "/tts")
EXEMPT_PATHS = ("/health", "/debug/events")  # the launcher's probe and the log panel's poll
MAX_CLIENTS = 2000  # buckets kept; the oldest are dropped past this, so the table cannot grow without bound


def group_of(path: str) -> str | None:
    """The limit group of a path, or None when it is not limited."""
    if path in EXEMPT_PATHS:
        return None
    if path.startswith(MODEL_PATHS):
        return "model"
    if path.startswith(SPEECH_PATHS):
        return "speech"
    return "other"


def limits_from(text: str | None) -> dict[str, int] | None:
    """The limits from PULSAR_RATE_LIMITS: None when off, the defaults when unset, else the defaults with the overrides."""
    if text is None or not text.strip():
        return dict(DEFAULT_LIMITS)
    if text.strip().lower() == "off":
        return None
    limits = dict(DEFAULT_LIMITS)
    for pair in text.split(","):
        name, _, value = pair.partition("=")
        if name.strip() not in limits or not value.strip().isdigit() or int(value) < 1:
            raise ValueError(f"PULSAR_RATE_LIMITS: {pair.strip()!r} is not one of {sorted(limits)} with a positive number")
        limits[name.strip()] = int(value)
    return limits


@dataclass
class _Bucket:
    tokens: float
    at: float


class RateLimiter:
    """Token buckets by (client, group). `check` returns 0 when the request may pass, else the seconds to wait."""

    def __init__(self, limits: dict[str, int] | None, clock=time.monotonic) -> None:
        self.limits = limits
        self._clock = clock
        self._buckets: dict[tuple[str, str], _Bucket] = {}
        self._lock = threading.Lock()

    def check(self, client: str, path: str) -> int:
        group = group_of(path) if self.limits else None
        if group is None:
            return 0
        per_minute = self.limits[group]
        burst = max(5.0, per_minute / 4)
        rate = per_minute / 60.0
        now = self._clock()
        with self._lock:
            bucket = self._buckets.pop((client, group), None) or _Bucket(burst, now)
            bucket.tokens = min(burst, bucket.tokens + (now - bucket.at) * rate)
            bucket.at = now
            self._buckets[(client, group)] = bucket  # re-inserted last: the dict's order is the order of use
            while len(self._buckets) > MAX_CLIENTS:
                self._buckets.pop(next(iter(self._buckets)))
            if bucket.tokens >= 1:
                bucket.tokens -= 1
                return 0
            return max(1, math.ceil((1 - bucket.tokens) / rate))


def from_environment() -> RateLimiter:
    return RateLimiter(limits_from(os.environ.get("PULSAR_RATE_LIMITS")))
