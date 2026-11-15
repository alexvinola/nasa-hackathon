#!/usr/bin/env bash
# G8's check (`make check-G8`): the demo starts with one command and the goals it shows are green.
#
#   scripts/check_demo.sh                 # goals G0 to G7, then ./start_synapse --check
#   DEMO_GOALS="G0 G3 G4 G5" scripts/check_demo.sh   # after a goal has been cut (goals/G8-demo.md: "that have not been cut")
#
# Order: the goal checks run first and the services start afterwards. The browser checks (Playwright) start their
# own Next.js dev server, and Next.js refuses a second one in the same folder, so they cannot run while the demo is
# up. For the same reason this script refuses to start when the demo is already running from this checkout.
#
# What it does NOT check: the timed rehearsal with Wi-Fi off (docs/rehearsals.md). That part of G8 is done by people.
set -uo pipefail
cd "$(dirname "$0")/.."

GOALS="${DEMO_GOALS:-G0 G1 G2 G3 G4 G5 G6 G7}"
FRONTEND_URL="http://localhost:3000"

answers() { curl -fs -m 3 -o /dev/null "$1"; }

if answers "$FRONTEND_URL/"; then
  echo "ERROR: something already answers at $FRONTEND_URL. Stop the demo (Ctrl+C in ./start_synapse) and run this again:" >&2
  echo "       the browser checks need to start their own Next.js dev server." >&2
  exit 1
fi

failed=0

echo "== 1/2  goal checks: $GOALS"
# shellcheck disable=SC2086  # the list is split into one argument per goal on purpose
if ! uv run --quiet python scripts/goals.py $GOALS; then
  failed=1
fi

echo
echo "== 2/2  ./start_synapse --check  (Ollama 11434, FastAPI 8000, Next.js 3000, then stop)"
if ./start_synapse --check; then
  echo "start: the three services answered their health checks"
else
  echo "start: FAILED"
  failed=1
fi

echo
if [[ $failed == 0 ]]; then
  echo "G8 check: goals green and the demo starts. Still to do by hand: the timed rehearsal with Wi-Fi off (docs/rehearsals.md)."
else
  echo "G8 check: NOT passed (see above)."
fi
exit $failed
