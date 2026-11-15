"""Paths and process-level settings. Everything runs on localhost; nothing here points off the machine."""

import os
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
ASSETS_DIR = BACKEND_DIR / "assets"

# Per-developer overrides, e.g. PULSAR_LLM_MODEL=gemma4:e2b-it-qat on a laptop with under 16 GB of RAM, from the
# repository's git-ignored `.env` (KEY=value lines). A variable already in the environment wins, and the default model
# stays the one the team runs.
_ENV_FILE = BACKEND_DIR.parent / ".env"
if _ENV_FILE.is_file():
    for _line in _ENV_FILE.read_text(encoding="utf-8").splitlines():
        _key, _sep, _value = _line.partition("=")
        if _sep and not _line.lstrip().startswith("#"):
            os.environ.setdefault(_key.strip(), _value.strip().strip("\"'"))

# The contract, sources and HRP names live in the repository's shared/ folder (single source of truth).
SHARED_DIR = Path(os.environ.get("PULSAR_SHARED_DIR", BACKEND_DIR.parent / "shared")).resolve()

RULES_FILE = Path(os.environ.get("PULSAR_RULES_FILE", ASSETS_DIR / "rules.json")).resolve()
COUNTERMEASURES_FILE = Path(os.environ.get("PULSAR_COUNTERMEASURES_FILE", ASSETS_DIR / "countermeasures.json")).resolve()

# Browser origins allowed to call the API (the Next.js dev server). Comma-separated.
CORS_ORIGINS = [
    origin.strip()
    for origin in os.environ.get("PULSAR_CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",")
    if origin.strip()
]


def allowed_origins(text: str | None) -> frozenset[str]:
    """PULSAR_ALLOWED_ORIGINS as the set of values the local-only check accepts besides this machine.

    Each entry is the origin of a page the HUD is deliberately served from, e.g. `https://pulsar.example.org`.
    Both the origin and its host are accepted, because a browser sends the first in `Origin` and a proxy passes
    the second in `Host`. An entry without `https://` (or `http://`) and a host is a configuration error.
    """
    accepted: set[str] = set()
    for entry in (text or "").split(","):
        origin = entry.strip().rstrip("/")
        if not origin:
            continue
        scheme, separator, host = origin.partition("://")
        if scheme not in ("http", "https") or not separator or not host or "/" in host:
            raise ValueError(f"PULSAR_ALLOWED_ORIGINS: {entry.strip()!r} is not an origin like https://pulsar.example.org")
        accepted.update((origin, host))
    return frozenset(accepted)


# Pages served from somewhere other than this machine that may still use the speech, vision and director endpoints.
# Empty by default: PULSAR is local and offline, and every laptop keeps it that way. A hosted copy names its own
# address here, which is a deliberate exception to "nothing leaves the machine" for that server only.
ALLOWED_ORIGINS = allowed_origins(os.environ.get("PULSAR_ALLOWED_ORIGINS"))

# The language PULSAR answers in when a request does not say ("es" or "en"). The front sends its own choice.
LANGS = ("es", "en")
DEFAULT_LANG = os.environ.get("PULSAR_LANG", "es") if os.environ.get("PULSAR_LANG", "es") in LANGS else "es"
I18N_DIR = ASSETS_DIR / "i18n"


def pick_lang(lang: str | None) -> str:
    """The language of a request: the one asked for when we have it, else the default."""
    return lang if lang in LANGS else DEFAULT_LANG
