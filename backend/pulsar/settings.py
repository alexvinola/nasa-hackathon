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
