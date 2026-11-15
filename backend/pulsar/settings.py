"""Paths and process-level settings. Everything runs on localhost; nothing here points off the machine."""

import os
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
ASSETS_DIR = BACKEND_DIR / "assets"

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

# The language PULSAR answers in when a request does not say ("es" or "en"). The front sends its own choice.
LANGS = ("es", "en")
DEFAULT_LANG = os.environ.get("PULSAR_LANG", "es") if os.environ.get("PULSAR_LANG", "es") in LANGS else "es"
I18N_DIR = ASSETS_DIR / "i18n"


def pick_lang(lang: str | None) -> str:
    """The language of a request: the one asked for when we have it, else the default."""
    return lang if lang in LANGS else DEFAULT_LANG
