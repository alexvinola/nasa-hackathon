"""PULSAR's senses, all on this machine: speech to text (faster-whisper), text to speech (Piper)
and a plain description of one camera frame (a vision model served by Ollama on localhost).

Nothing is stored: audio and frames live only for the request. The description is only a description:
it never feeds the rules engine and never states a status, a diagnosis or an escalation.
"""

import base64
import io
import json
import os
import re
import threading
import time
import urllib.error
import urllib.request
import wave
from functools import cache
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field

from pulsar import debug

LOCAL = re.compile(r"(https?://)?(localhost|127\.0\.0\.1)(:\d+)?")


def local_only(request: Request) -> None:
    """CORS only hides answers. A browser names the calling page in Origin and, under DNS rebinding, a foreign Host."""
    for header in ("origin", "host"):
        value = request.headers.get(header)
        if value and not LOCAL.fullmatch(value):
            raise HTTPException(403, "PULSAR only answers pages served from this machine")


router = APIRouter(dependencies=[Depends(local_only)])

VOICE = Path(os.environ.get("PULSAR_VOICE", Path(__file__).parent / "assets/voices/es_ES-davefx-medium.onnx"))
# Multilingual so the astronaut can speak Spanish; about twice as slow as base.en (set that for an English-only crew).
WHISPER_MODEL = os.environ.get("PULSAR_WHISPER_MODEL", "base")
OLLAMA_URL = os.environ.get("PULSAR_OLLAMA_URL", "http://127.0.0.1:11434")
VISION_MODEL = os.environ.get("PULSAR_LLM_MODEL", "gemma4:e4b-it-qat")
MAX_AUDIO = 10 * 1024 * 1024
MAX_IMAGE = 2 * 1024 * 1024

# Ollama unloads an idle model after 5 minutes by default, and reloading it is the slowest thing it does.
KEEP_ALIVE = "30m"

VISION_PROMPT = (
    "You are the eyes of PULSAR, a companion robot for astronauts. Look at the camera frame and report only what is "
    "clearly visible, in one or two short sentences: how many people, where they are in the picture (left, right or "
    "centre), their posture and what they are doing, any object they hold or use, and any readable text. "
    "Be specific and name things; if something is unclear, leave it out rather than guess. "
    "Only describe. Do not diagnose, do not judge health, fatigue or mood, do not give advice and do not use digits."
)


async def read_body(request: Request, limit: int, kind: str) -> bytes:
    body = bytearray()
    async for chunk in request.stream():  # stop reading at the limit instead of buffering whatever is sent
        body += chunk
        if len(body) > limit:
            raise HTTPException(413, f"{kind} larger than {limit // 1024 // 1024} MB")
    if not body:
        raise HTTPException(400, f"empty {kind}")
    return bytes(body)


@cache
def whisper():
    from faster_whisper import WhisperModel

    return WhisperModel(WHISPER_MODEL, device="cpu", compute_type="int8")


@cache
def voice():
    from piper import PiperVoice

    return PiperVoice.load(VOICE)


def transcribe(audio: bytes) -> str:
    model = whisper()
    try:
        # The VAD drops silence, which whisper otherwise "hears" as short made-up words ("You", "Thank you.").
        segments, _ = model.transcribe(io.BytesIO(audio), vad_filter=True, condition_on_previous_text=False)
        return " ".join(segment.text.strip() for segment in segments)
    except Exception as error:  # PyAV raises its own family of errors for anything it cannot decode
        raise HTTPException(422, f"could not decode the audio: {error}") from error


speaking = threading.Lock()


def synthesize(text: str) -> bytes:
    if not VOICE.exists():
        raise HTTPException(503, f"Piper voice missing at {VOICE}: run make prefetch")
    buffer = io.BytesIO()
    with speaking, wave.open(buffer, "wb") as wav:  # one utterance at a time: Piper's phonemizer is not thread-safe
        voice().synthesize_wav(text, wav)
    return buffer.getvalue()


def chat_message(messages: list[dict], **extra) -> dict:
    """One reply message from the local model (with its `tool_calls`, if any). `extra` adds Ollama fields such as
    `options`, `format` or `tools`."""
    payload = {
        "model": VISION_MODEL,
        "stream": False,
        "think": False,  # on by default in Gemma 4 and it would eat the short answer budget (research/llm/README.md)
        "keep_alive": KEEP_ALIVE,
        "messages": messages,
        **extra,
        # Every call must ask for the same context size, or Ollama reloads the model. PULSAR's prompts stay far
        # below this, and half the default context is memory the laptop gets back.
        "options": {"num_ctx": 2048, **extra.get("options", {})},
    }
    request = urllib.request.Request(
        f"{OLLAMA_URL}/api/chat", data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"}
    )
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            message = json.load(response)["message"]
        tools = ", ".join(call.get("function", {}).get("name", "?") for call in message.get("tool_calls") or [])
        said = message.get("content", "").strip() or (f"calls {tools}" if tools else "(empty)")
        debug.record("gemma", f"{round((time.perf_counter() - started) * 1000)} ms → {said}")
        return message
    except urllib.error.HTTPError as error:  # e.g. the model has not been pulled
        raise HTTPException(502, f"Ollama refused the request: {error.read().decode(errors='replace')}") from error
    except (urllib.error.URLError, TimeoutError) as error:
        raise HTTPException(503, f"Ollama is not answering at {OLLAMA_URL}: start it and pull {VISION_MODEL}") from error


def chat(messages: list[dict], **extra) -> str:
    """One answer from the local model, as text."""
    return chat_message(messages, **extra)["content"].strip()


def warm_up() -> None:
    """Loads the models ahead of the first question (each takes seconds); a missing one is not an error here."""
    for load in (whisper, lambda: VOICE.exists() and voice(), lambda: chat([])):
        try:
            load()
        except Exception:
            pass


def describe(image: bytes) -> str:
    return chat(
        [
            {"role": "system", "content": VISION_PROMPT},
            {
                "role": "user",
                "content": "What is happening in this camera frame?",
                "images": [base64.b64encode(image).decode()],
            },
        ],
        options={"temperature": 0.2, "num_predict": 200},
    )


class Say(BaseModel):
    text: str = Field(min_length=1, max_length=600)


@router.post("/stt")
async def speech_to_text(request: Request) -> dict[str, str]:
    """Body: an audio file (wav, webm/opus, mp3...). Returns its transcript."""
    audio = await read_body(request, MAX_AUDIO, "audio")
    text = await run_in_threadpool(transcribe, audio)
    debug.record("voice", f"heard: {text or '(nothing)'}")
    return {"text": text}


@router.post("/tts")
async def text_to_speech(say: Say) -> Response:
    """Returns the text spoken by Piper as a WAV file."""
    return Response(await run_in_threadpool(synthesize, say.text), media_type="audio/wav")


@router.post("/vision/describe")
async def describe_frame(request: Request) -> dict[str, str]:
    """Body: one JPEG frame. Returns what the vision model sees, in at most two sentences."""
    image = await read_body(request, MAX_IMAGE, "image")
    if not image.startswith(b"\xff\xd8"):
        raise HTTPException(415, "the frame must be a JPEG")
    return {"description": await run_in_threadpool(describe, image)}
