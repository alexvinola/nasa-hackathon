"""Offline voice pipeline (goal G5). Boundary only: nothing here is implemented or wired to the app yet.

G5's acceptance test (`backend/tests/acceptance/test_voice.py`) must be written and approved by the human
before any code lands here. This docstring fixes where that code goes and what it may and may not do.

Pipeline, all on localhost with no network (`HF_HUB_OFFLINE=1`):

    audio (wav) --faster-whisper (int8)--> transcript
              --pulsar.rules.RulesEngine--> decision        (the engine decides; unchanged)
              --Gemma 4 via local Ollama--> at most 2 sentences phrasing that decision
              --Piper TTS (assets/voices/)--> audio

Rules for the LLM stage (product rules in CLAUDE.md):
- Gemma never decides a status, an escalation or a risk. It receives the decision the rules engine already
  produced and only phrases it; the PULSAR prompt goes in the system message, the verdict in the user message.
- The answer is at most 2 sentences and mentions no figure or diagnosis absent from the verdict.
- Speech-to-text stays with faster-whisper: Ollama exposes Gemma 4 with text and image input only.

Interface it will expose (to be confirmed by the G5 acceptance test):

    transcribe(audio: bytes) -> str
    phrase(decision: dict, transcript: str) -> str          # LLM; phrasing only
    synthesize(text: str) -> bytes                           # wav
    respond(audio: bytes, telemetry: dict) -> VoiceTurn      # transcript, decision, text, audio, per-stage latency

plus an HTTP route under /voice and `backend/scripts/voice_bench.py`, which writes `backend/bench/voice_latency.json`.
Those latencies are the only ones that may be quoted in the pitch.

Configuration: `pulsar.voice.config` (model tag and Ollama URL from the environment, localhost only).
"""
