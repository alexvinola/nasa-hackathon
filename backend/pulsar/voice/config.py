"""Voice pipeline configuration, read from the environment. Nothing here loads a model or opens a connection.

- PULSAR_LLM_MODEL   Ollama tag of the phrasing model. Default `gemma4:e4b-it-qat` (Gemma 4 E4B, 6.1 GB);
                     use `gemma4:e2b-it-qat` on a laptop with under 16 GB of RAM.
- PULSAR_OLLAMA_URL  Ollama endpoint. Must point at this machine: no data leaves the laptop.
- PULSAR_VOICES_DIR  Folder with the Piper voices (`make prefetch` downloads them).
"""

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from pulsar.settings import ASSETS_DIR

DEFAULT_LLM_MODEL = "gemma4:e4b-it-qat"
DEFAULT_OLLAMA_URL = "http://127.0.0.1:11434"
LOCAL_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})


@dataclass(frozen=True)
class VoiceSettings:
    llm_model: str
    ollama_url: str
    voices_dir: Path


def load_voice_settings(env: Mapping[str, str] | None = None) -> VoiceSettings:
    env = os.environ if env is None else env
    ollama_url = env.get("PULSAR_OLLAMA_URL", DEFAULT_OLLAMA_URL).rstrip("/")
    parsed = urlparse(ollama_url)
    if parsed.scheme not in {"http", "https"} or parsed.hostname not in LOCAL_HOSTS:
        raise ValueError(f"PULSAR_OLLAMA_URL must point at this machine (localhost), got {ollama_url!r}")
    return VoiceSettings(
        llm_model=env.get("PULSAR_LLM_MODEL", DEFAULT_LLM_MODEL).strip() or DEFAULT_LLM_MODEL,
        ollama_url=ollama_url,
        voices_dir=Path(env.get("PULSAR_VOICES_DIR", ASSETS_DIR / "voices")).resolve(),
    )
