# PULSAR — every goal in GOALS.md has its check-Gn. A goal is done when its
# check passes; there is no other status. `make goals` prints the scoreboard.

SHELL := /bin/bash
# Windows: outside Git Bash, make falls back to cmd.exe and every recipe breaks, so point it at Git Bash.
# Override with `make GIT_BASH=C:/path/to/bash.exe ...` if Git lives somewhere else (no spaces in the path).
ifeq ($(OS),Windows_NT)
GIT_BASH ?= $(firstword $(wildcard C:/Progra~1/Git/bin/bash.exe $(subst \,/,$(LOCALAPPDATA))/Programs/Git/bin/bash.exe))
ifneq ($(GIT_BASH),)
SHELL := $(GIT_BASH)
endif
endif
.SHELLFLAGS := -eu -o pipefail -c
.PHONY: goals contract sources model start prefetch $(addprefix check-G,0 1 2 3 4 5 6 7 8 9 10 11)

BACKEND_TEST := cd backend && uv run --quiet pytest -q -p no:cacheprovider
FRONT_UNIT   := cd frontend && pnpm -s vitest run
FRONT_E2E    := cd frontend && pnpm -s playwright test

# $(call need,path...) fails with a clear message when something the goal must create is missing
need = for f in $(1); do test -e "$$f" || { echo "MISSING: $$f"; exit 1; }; done

goals:
	@uv run --quiet python scripts/goals.py

contract:
	@uv run --quiet --with jsonschema python scripts/check_contract.py

sources:
	@uv run --quiet python scripts/provenance.py

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

check-G9:
	@$(call need,shared/indicators.json frontend/src/acceptance/indicators.test.ts frontend/e2e/acceptance/g9-guides.spec.ts)
	@$(FRONT_UNIT) src/acceptance/indicators.test.ts
	@$(FRONT_E2E) e2e/acceptance/g9-guides.spec.ts

check-G10:
	@$(call need,backend/assets/emergency.json backend/tests/acceptance/test_emergency.py)
	@$(BACKEND_TEST) tests/acceptance/test_emergency.py

check-G11: check-G1
	@$(call need,frontend/e2e/acceptance/g11-camera-source.spec.ts)
	@$(FRONT_E2E) e2e/acceptance/g11-camera-source.spec.ts

model:
	@$(call need,data/pyproject.toml data/pipeline.py)
	@cd data && uv run --quiet python pipeline.py

start:
	@./start_synapse

prefetch:
	@scripts/prefetch.sh
