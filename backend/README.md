# PULSAR backend

FastAPI on localhost. The **rules engine decides** (status, escalation, affected systems, HRP risk,
countermeasure); the implemented local voice pipeline only phrases that decision. Source presence does not
prove G5's offline/latency acceptance. Not a medical device.

## Run

```bash
cd backend
uv sync                          # Python 3.12, deps from uv.lock
uv run uvicorn main:app          # http://127.0.0.1:8000, docs at /docs
uv run pytest -q                 # unit + acceptance tests
cd ..
make check-G4                    # G4's exact acceptance check
make check-G5                    # voice acceptance: local models/prerequisites required
```

## Endpoints

| Method | Path | What |
|---|---|---|
| POST | `/rules/evaluate` | Full telemetry contract in, `decision` block out. 422 if it breaks `shared/telemetry.schema.json`. The incoming `decision` is ignored. |
| GET | `/rules` | Every rule: `id, signal, operator, threshold, unit, status, hazard, hrpRisk, bodySystems, countermeasureId, source, assumption, message`, plus the official `hazardName` / `hrpRiskName`. |
| GET | `/rules/policy` | How triggered rules combine into one decision. |
| GET | `/countermeasures`, `/countermeasures/{id}` | Short steps for each countermeasure. |
| GET | `/health` | Liveness probe. |
| POST | `/voice/advise` | `{telemetry, question?}` in; engine `decision`, `say`, `source`, `violations` out. 422 for invalid telemetry; 503 when the phrasing model is unavailable. |

## Layout

```
main.py                     exposes `app`
pulsar/app.py               app factory (CORS for the Next.js dev server, routers)
pulsar/settings.py          paths; PULSAR_SHARED_DIR, PULSAR_RULES_FILE, PULSAR_CORS_ORIGINS
pulsar/shared.py            reads shared/: schema enums, source ids, official HRP names (never copied)
pulsar/contract.py          JSON Schema validation of the telemetry and of the decision
pulsar/rules/               rules engine: models, loader (checks against shared/), engine (policy), api
pulsar/voice/               local voice pipeline, phrasing API and configuration
assets/rules.json           the rules and the aggregation policy (data, shown to the judges)
assets/countermeasures.json the steps each rule points to
tests/acceptance/           protected: the goal checks (do not edit to make them pass)
tests/unit/                 our own tests of the policy, the loader and the API
```

See [implementation status](../docs/IMPLEMENTATION.md) for missing goals and
[the harness guide](../docs/HARNESS.md) for agent routing and exact checks.
Download/cache models during preparation, then verify with connectivity disabled;
mocked tests are not evidence of offline model readiness.

## Where the rules live

`assets/rules.json`. Each rule compares one contract signal with one threshold:

```json
{
  "id": "sleep-under-6h",
  "signal": "selfReport.sleepHoursLast24h",
  "operator": "<",
  "threshold": 6,
  "unit": "h",
  "status": "AMBER",
  "hazard": "ISOLATION",
  "hrpRisk": "SLEEP_AND_SCHEDULES",
  "bodySystems": ["NERVOUS"],
  "countermeasureId": "CM-FATIGUE-01",
  "source": "jones-2022-sleep",
  "assumption": null,
  "message": "Slept {value} {unit} in the last 24 h, under {threshold} {unit}: in astronauts this went with slower reactions."
}
```

Aggregation (also in the file, `policy`, and in `pulsar/rules/engine.py`):

- **Status**: the most severe triggered rule; GREEN when none. A null signal triggers nothing.
- **Escalation**: follows the status (GREEN → SELF_CARE, AMBER → CREW, RED → FLIGHT_SURGEON). Team assumption.
- **Affected systems**: union of the triggered rules' body systems.
- **HRP risk**: among triggered rules that name a risk, keep the most severe; pick the risk most of them name;
  ties go to the rule listed first. Null when none names a risk (cabin CO2 has no official HRP risk).
- **Countermeasure**: that of the most severe triggered rule, first listed on a tie. Rule order is priority.

## How to add a rule

1. Pick a numeric field of the contract as `signal` (dotted path).
2. Cite the threshold: `source` must be an id in `shared/sources.json` (add the source there first, then
   `make sources`). If there is none, set `source: null` and say why the number is what it is in `assumption`.
3. Use official ids only: `hazard` and `hrpRisk` from `shared/hrp.json` (or null), `bodySystems` from the contract.
4. Point `countermeasureId` at an entry in `assets/countermeasures.json` (add one if needed: short, modest steps).
5. Write a short plain-English `message` with `{value}`, `{threshold}` and `{unit}`.
6. Place it in the list by priority and run `uv run pytest -q`. The app refuses to start if any id does not
   trace back to `shared/`.
