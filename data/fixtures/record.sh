#!/usr/bin/env bash
# Records G1's two fixture videos from the Mac's camera and converts them to the .y4m Chromium plays as a fake
# camera (goals/G1-camera-fatigue.md). Same lighting as the venue, face centred, 12 s each.
#
#   data/fixtures/record.sh            # records both, one after the other
#   data/fixtures/record.sh alert      # only one: alert or eyes_closed
#   CAMERA=1 data/fixtures/record.sh   # another camera (ffmpeg -f avfoundation -list_devices true -i "")
#
# The .mp4 is the small source; the .y4m (raw, ~120 MB) is rebuilt from it with `record.sh convert`.
# These are faces: whoever is recorded must agree, and the repository will be public.
set -euo pipefail
cd "$(dirname "$0")"

CAMERA="${CAMERA:-0}"
SECONDS_LONG=12

convert() {
  ffmpeg -loglevel error -y -i "$1.mp4" -vf "scale=640:360" -pix_fmt yuv420p -r 30 "$1.y4m"
  echo "wrote data/fixtures/$1.y4m"
}

record() {
  local name=$1 what=$2
  echo
  echo "== $name: $what"
  read -r -p "   Press Enter when ready; recording lasts ${SECONDS_LONG} s. "
  ffmpeg -loglevel error -y -f avfoundation -framerate 30 -video_size 1280x720 -i "$CAMERA" \
    -t "$SECONDS_LONG" -an -c:v libx264 -crf 23 -pix_fmt yuv420p "$name.mp4"
  convert "$name"
}

case "${1:-all}" in
  alert) record alert "look at the screen, eyes open, blink normally" ;;
  eyes_closed) record eyes_closed "keep your eyes closed the whole time, head still" ;;
  convert) for name in alert eyes_closed; do [ -f "$name.mp4" ] && convert "$name"; done ;;
  all)
    record alert "look at the screen, eyes open, blink normally"
    record eyes_closed "keep your eyes closed the whole time, head still"
    ;;
  *) echo "usage: $0 [alert|eyes_closed|convert|all]" >&2; exit 2 ;;
esac
