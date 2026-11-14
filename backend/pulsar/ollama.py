"""The one way the backend talks to Gemma: the local Ollama in `pulsar.voice.config` (localhost only)."""

import json
import urllib.request
from typing import Any

from pulsar.voice.config import load_voice_settings


def chat(messages: list[dict[str, Any]], *, options: dict[str, Any] | None = None, fmt: dict[str, Any] | None = None,
         timeout: float = 120) -> str:
    """One non-streamed answer. `fmt` is a JSON schema for structured output. Raises OSError if Ollama is down."""
    settings = load_voice_settings()
    payload: dict[str, Any] = {
        "model": settings.llm_model,
        "stream": False,
        "think": False,  # on by default in Gemma 4; it only adds latency to short answers
        "keep_alive": "30m",
        # Same context size as senses.chat: Ollama reloads the model (seconds) whenever a call asks for another one.
        "options": {"num_ctx": 2048, **(options or {})},
        "messages": messages,
    }
    if fmt is not None:
        payload["format"] = fmt
    request = urllib.request.Request(f"{settings.ollama_url}/api/chat", data=json.dumps(payload).encode(),
                                     headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.load(response)["message"]["content"].strip()
