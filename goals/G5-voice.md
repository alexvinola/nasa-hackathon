# G5 · Offline voice

Owner: FS2 · Branch: `goal/G5-voice` · Depends on: G4, downloaded models (`make prefetch`)

## Goal
From audio to a spoken answer on the demo laptop with no network: faster-whisper → rules engine → Gemma 4 E2B (Ollama `gemma4:e2b-it-qat`) → Piper.

## Done when
- `backend/scripts/voice_bench.py` plays each `.wav` in `data/fixtures/voice/`, gets text and audio back, and writes `backend/bench/voice_latency.json` with per-stage latency (STT, rules, LLM, TTS) and total.
- It works with networking disabled (`HF_HUB_OFFLINE=1`, Ollama on localhost).
- Gemma's answer is at most 2 sentences and mentions no figures or diagnoses absent from the verdict (checked automatically over the G4 scenarios).

## Check
`make check-G5` → `backend/tests/acceptance/test_voice.py` (runs the bench and validates the JSON and the prompt rules).

## Notes
The latency figures produced here are the only ones that may be quoted in the pitch.
- The model tag comes from config (`PULSAR_LLM_MODEL`, default `gemma4:e2b-it-qat`). If the bench shows room on the demo
  laptop with whisper, Piper and the browser running, try `gemma4:e4b-it-qat` (6.1 GB) and keep whichever passes.
- Gemma 4 supports the system role natively: the PULSAR prompt goes in the system message, the verdict in the user message.
- Gemma 4 E2B/E4B accept audio in Google's release, but Ollama lists text and image input only: speech-to-text stays
  with faster-whisper.
