"""PULSAR backend.

Two modules behind one FastAPI app (`pulsar.app.create_app`):

- `pulsar.rules`: the rules engine. Telemetry in, decision out. It is the only component that decides
  status, escalation, affected systems and HRP risk; its rules live in data (`assets/rules.json`).
- `pulsar.voice`: the offline voice pipeline (faster-whisper -> rules engine -> Gemma via local Ollama -> Piper).
  Only its boundary and configuration exist for now; G5 implements it once its acceptance test is approved.

`shared/` (telemetry schema, sources, HRP names) is the single source of truth and is read at runtime
through `pulsar.shared`; nothing from it is copied into the backend.
"""
