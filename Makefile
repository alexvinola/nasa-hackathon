# S.Y.N.A.P.S.E. — every goal in GOALS.md has its check-Gn. A goal is done when its
# check passes; there is no other status. `make goals` prints the scoreboard.

SHELL := /bin/bash
.SHELLFLAGS := -eu -o pipefail -c
.PHONY: goals contract model start prefetch $(addprefix check-G,0 1 2 3 4 5 6 7 8)

BACKEND_TEST := cd backend && uv run --quiet pytest -q -p no:cacheprovider
FRONT_UNIT   := cd frontend && pnpm -s vitest run
FRONT_E2E    := cd frontend && pnpm -s playwright test

# $(call need,path...) fails with a clear message when something the goal must create is missing
need = for f in $(1); do test -e "$$f" || { echo "MISSING: $$f"; exit 1; }; done

goals:
	@uv run --quiet python scripts/goals.py

contract:
	@uv run --quiet --with jsonschema python scripts/check_contract.py

check-G0: contract
	@$(call need,backend/main.py frontend/package.json frontend/src/acceptance/contract.test.ts)
	@$(BACKEND_TEST) tests/acceptance/test_contract.py
	@$(FRONT_UNIT) src/acceptance/contract.test.ts

check-G1:
	@$(call need,frontend/e2e/acceptance/g1-fatigue.spec.ts data/fixtures/eyes_closed.y4m data/fixtures/alert.y4m)
	@$(FRONT_E2E) e2e/acceptance/g1-fatigue.spec.ts

check-G2: model
	@$(call need,data/acceptance/check_model.py)
	@cd data && uv run --quiet python acceptance/check_model.py

check-G3:
	@$(call need,frontend/src/acceptance/pvt.test.ts)
	@$(FRONT_UNIT) src/acceptance/pvt.test.ts

check-G4: contract
	@$(call need,backend/main.py)
	@$(BACKEND_TEST) tests/acceptance/test_rules_scenarios.py

check-G5:
	@$(call need,backend/tests/acceptance/test_voice.py backend/scripts/voice_bench.py)
	@$(BACKEND_TEST) tests/acceptance/test_voice.py

check-G6:
	@$(call need,frontend/e2e/acceptance/g6-twin.spec.ts)
	@$(FRONT_E2E) e2e/acceptance/g6-twin.spec.ts

check-G7:
	@$(call need,frontend/e2e/acceptance/g7-intro.spec.ts)
	@$(FRONT_E2E) e2e/acceptance/g7-intro.spec.ts

check-G8:
	@$(call need,start_synapse scripts/check_demo.sh)
	@scripts/check_demo.sh

model:
	@$(call need,data/pyproject.toml data/pipeline.py)
	@cd data && uv run --quiet python pipeline.py

start:
	@./start_synapse

prefetch:
	@scripts/prefetch.sh
