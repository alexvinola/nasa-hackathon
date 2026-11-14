"""PULSAR's senses, all on this machine: speech to text (faster-whisper), text to speech (Piper)
and a plain description of one camera frame (a vision model served by Ollama on localhost).

Nothing is stored: audio and frames live only for the request. The description is only a description:
it never feeds the rules engine and never states a status, a diagnosis or an escalation.
"""

import base64
import io
import json
import os
import urllib.error
import urllib.request
import wave
from functools import cache
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field

router = APIRouter()

VOICE = Path(os.environ.get("PULSAR_VOICE", Path(__file__).parent / "assets/voices/en_US-lessac-medium.onnx"))
WHISPER_MODEL = os.environ.get("PULSAR_WHISPER_MODEL", "base.en")
OLLAMA_URL = os.environ.get("PULSAR_OLLAMA_URL", "http://127.0.0.1:11434")
VISION_MODEL = os.environ.get("PULSAR_LLM_MODEL", "gemma4:e4b-it-qat")
MAX_AUDIO = 10 * 1024 * 1024
MAX_IMAGE = 2 * 1024 * 1024

VISION_PROMPT = (
    "You are the eyes of PULSAR, a companion for astronauts. Describe what is visible in the camera frame in at "
    "most two short sentences: who is there, their posture, what they are doing and the surroundings. "
    "Only describe. Do not diagnose, do not judge health, fatigue or mood, do not give advice and do not use numbers."
)


async def read_body(request: Request, limit: int, kind: str) -> bytes:
    body = await request.body()
    if not body:
        raise HTTPException(400, f"empty {kind}")
    if len(body) > limit:
        raise HTTPException(413, f"{kind} larger than {limit // 1024 // 1024} MB")
    return body


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
        segments, _ = model.transcribe(io.BytesIO(audio))
        return " ".join(segment.text.strip() for segment in segments)
    except Exception as error:  # PyAV raises its own family of errors for anything it cannot decode
        raise HTTPException(422, f"could not decode the audio: {error}") from error


def synthesize(text: str) -> bytes:
    if not VOICE.exists():
        raise HTTPException(503, f"Piper voice missing at {VOICE}: run make prefetch")
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav:
        voice().synthesize_wav(text, wav)
    return buffer.getvalue()


def describe(image: bytes) -> str:
    payload = {
        "model": VISION_MODEL,
        "stream": False,
        "options": {"temperature": 0.2, "num_predict": 200},
        "think": False,  # e4b is a thinking model; its thinking block would swallow the whole budget
        "messages": [
            {"role": "system", "content": VISION_PROMPT},
            {
                "role": "user",
                "content": "What is happening in this camera frame?",
                "images": [base64.b64encode(image).decode()],
            },
        ],
    }
    request = urllib.request.Request(
        f"{OLLAMA_URL}/api/chat", data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            return json.load(response)["message"]["content"].strip()
    except urllib.error.HTTPError as error:  # e.g. the model has not been pulled
        raise HTTPException(502, f"Ollama refused the request: {error.read().decode(errors='replace')}") from error
    except (urllib.error.URLError, TimeoutError) as error:
        raise HTTPException(503, f"Ollama is not answering at {OLLAMA_URL}: start it and pull {VISION_MODEL}") from error


class Say(BaseModel):
    text: str = Field(min_length=1, max_length=600)


@router.post("/stt")
async def speech_to_text(request: Request) -> dict[str, str]:
    """Body: an audio file (wav, webm/opus, mp3...). Returns its transcript."""
    audio = await read_body(request, MAX_AUDIO, "audio")
    return {"text": await run_in_threadpool(transcribe, audio)}


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
