#!/usr/bin/env bash
# Downloads everything the demo needs to run offline. Idempotent: safe to re-run.
# Run it at home or as soon as you arrive, before the venue Wi-Fi gets saturated.
set -euo pipefail
cd "$(dirname "$0")/.."

fetch() {  # fetch <url> <destination>
  if [[ -s "$2" ]]; then echo "present      $2"; return; fi
  mkdir -p "$(dirname "$2")"
  echo "downloading  $2"
  curl -fL --retry 3 -o "$2.part" "$1" && mv "$2.part" "$2"
}

MP=https://storage.googleapis.com/mediapipe-models
fetch "$MP/face_landmarker/face_landmarker/float16/1/face_landmarker.task" frontend/public/mediapipe/face_landmarker.task
fetch "$MP/pose_landmarker/pose_landmarker_lite/float16/1/pose_landmarker_lite.task" frontend/public/mediapipe/pose_landmarker_lite.task
# MediaPipe's .wasm files come from the npm package; `make prefetch` copies them once pnpm has installed it.
if [[ -d frontend/node_modules/@mediapipe/tasks-vision/wasm ]]; then
  mkdir -p frontend/public/mediapipe/wasm
  cp -r frontend/node_modules/@mediapipe/tasks-vision/wasm/. frontend/public/mediapipe/wasm/
  echo "present      frontend/public/mediapipe/wasm"
else
  echo "WARNING: run (cd frontend && pnpm install) first, then re-run to copy the MediaPipe wasm files" >&2
fi

PIPER=https://huggingface.co/rhasspy/piper-voices/resolve/main
for voice in en/en_US/lessac/medium/en_US-lessac-medium en/en_US/amy/medium/en_US-amy-medium; do
  fetch "$PIPER/$voice.onnx" "backend/assets/voices/$(basename "$voice").onnx"
  fetch "$PIPER/$voice.onnx.json" "backend/assets/voices/$(basename "$voice").onnx.json"
done

if command -v ollama >/dev/null; then
  pgrep -x ollama >/dev/null || (ollama serve >/dev/null 2>&1 &) && sleep 2
  ollama pull "${PULSAR_LLM_MODEL:-gemma4:e4b-it-qat}" || { echo "ERROR: Gemma 4 needs a current Ollama (0.22.1 fails): brew upgrade ollama, then re-run" >&2; exit 1; }
else
  echo "WARNING: install Ollama (brew install ollama) and re-run"
fi

# faster-whisper stores models in the Hugging Face cache; once it is filled, HF_HUB_OFFLINE=1 works.
uv run --quiet --python 3.12 --with faster-whisper python -c "
from faster_whisper import WhisperModel
for size in ('base.en', 'small.en'):
    WhisperModel(size, device='cpu', compute_type='int8'); print('whisper', size, 'ok')
"

echo "done: models and voices available locally"
