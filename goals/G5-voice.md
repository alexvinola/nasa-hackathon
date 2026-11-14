# G5 · Offline voice

Owner: FS2 · Branch: `goal/G5-voice` · Depends on: G4, downloaded models (`make prefetch`)

## Goal
From audio to a spoken answer on the demo laptop with no network: faster-whisper → rules engine → Gemma 2 2B (Ollama) → Piper.

## Done when
- `backend/scripts/voice_bench.py` plays each `.wav` in `data/fixtures/voice/`, gets text and audio back, and writes `backend/bench/voice_latency.json` with per-stage latency (STT, rules, LLM, TTS) and total.
- It works with networking disabled (`HF_HUB_OFFLINE=1`, Ollama on localhost).
- Gemma's answer is at most 2 sentences and mentions no figures or diagnoses absent from the verdict (checked automatically over the G4 scenarios).

## Check
`make check-G5` → `backend/tests/acceptance/test_voice.py` (runs the bench and validates the JSON and the prompt rules).

## Notes
The latency figures produced here are the only ones that may be quoted in the pitch.
