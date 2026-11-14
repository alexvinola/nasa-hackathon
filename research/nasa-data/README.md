# NASA data, explained simply

What NASA actually gives us, what each piece means in plain words, which medical tests and conditions it relates to,
which patterns hold up, and how PULSAR uses it. Every number here comes from `findings/` (computed by the scripts in
this folder) or from a source in `shared/sources.json`.

```bash
research/nasa-data/fetch.sh                                                    # download (git-ignored raw/)
uv run --with pandas python research/nasa-data/labs.py > research/nasa-data/findings/labs.txt
uv run --with pypdf  python research/nasa-data/asrs.py > research/nasa-data/findings/asrs.txt
```

## What we have, at a glance

| Piece | Is it data? | What it gives PULSAR |
|---|---|---|
| Challenge resources (HRP hazards, risks, research; CSA pages) | No: context pages | The official vocabulary: 5 hazards, 17 risks (`shared/hrp.json`) and the "why" of each indicator |
| **Inspiration4 labs** (OSDR OSD-569, OSD-575) | **Yes: real crew blood tests** | Real values and lab reference ranges for 4 civilians before and after a 3-day orbital flight |
| **ASRS fatigue reports** | **Yes: 100 real incident reports** | How fatigue errors actually unfold: the forensic intro and the wording of alerts |
| Papers on astronaut sleep, PVT-B and space anemia | Aggregates only | Thresholds: under 6 h of sleep, 355 ms PVT lapses, red-cell destruction on long missions |
| PVT on ISS (data.nasa.gov) | Gone (404) | Nothing; the paper is the reference instead |
| Standard Measures, LSDA, OSDR raw genetics | Restricted | Nothing within a hackathon: they need a formal data request |

## 1. Inspiration4 blood tests

**What it is.** In 2021 four civilians (crew C001-C004) flew 3 days in orbit. Their blood was drawn 92, 44 and 3 days
before launch (L-92, L-44, L-3) and 1, 45, 82 and 194 days after return (R+1 ... R+194). NASA publishes the results
in its Open Science Data Repository, with the reference range the lab used for each value.

### Complete blood count (hemogram)

The most common blood test: it counts the cells in your blood.

| Value | In plain words | Too low / too high usually means | Space link |
|---|---|---|---|
| Red cells, hemoglobin, hematocrit | Cells that carry oxygen | Low: anemia (tired, short of breath). High: dehydration | **Space anemia**: on 6-month missions astronauts destroyed 54% more red cells than on Earth (`trudel-2022-hemolysis`) |
| MCV, MCH, RDW | Size of the red cells, hemoglobin in each, and how much the size varies | Small cells: e.g. iron deficiency. Large: e.g. B12 or folate deficiency | |
| White cells (WBC) and their types | The immune system's cells: neutrophils fight bacteria, lymphocytes viruses and remember them, monocytes clean up and drive inflammation, eosinophils react to allergies | Low: weaker defence. High: infection or inflammation | HRP *Risk of Altered Immune System Responses* |
| Platelets, MPV | Cells that plug wounds and form clots | Low: bleeding. High: clotting risk | |

### Comprehensive metabolic panel

A chemistry test of the blood's liquid part: sugar, salts, kidneys, liver and proteins.

| Value | In plain words | Too low / too high usually means | Space link |
|---|---|---|---|
| Glucose | Blood sugar, the body's fuel | Low: dizziness, confusion. High: stress response or diabetes | HRP *Risk of Inadequate Food and Nutrition*; PULSAR already has `selfReport.glucoseMgDl` |
| Sodium, potassium, chloride, CO2 (bicarbonate) | Salts that keep water balance, nerves, muscles and heart rhythm working; bicarbonate keeps the blood's acidity steady | Off-range: dehydration or overhydration, kidney problems, heart-rhythm risk (potassium) | Fluids shift towards the head in microgravity |
| BUN, creatinine, eGFR | Waste the kidneys remove; eGFR estimates how well they filter | High BUN/creatinine: dehydration or kidney trouble | |
| ALT, AST, ALP, bilirubin | Liver enzymes; ALP also comes from bone | High: liver strain; high ALP: also bone turnover | HRP *Risk of Spaceflight-Induced Bone Changes* (ALP, calcium) |
| Calcium | Mineral stored in bone | Off-range: bone, kidney or hormone problems | Bone loss releases calcium |
| Albumin, globulin, total protein | Blood proteins: albumin reflects nutrition and hydration, globulins include antibodies | Low albumin: poor nutrition or inflammation | |

### Serum cardiovascular panel

Proteins that rise or fall with inflammation and clotting: CRP and SAP (inflammation alarms), fibrinogen (clotting and
inflammation), haptoglobin (mops up hemoglobin from destroyed red cells, so it drops when red cells break down),
AGP and alpha-2-macroglobulin (acute-phase proteins), PF4 (platelet activation), L-selectin (white cells sticking to
vessel walls), fetuin-A (prevents calcium deposits in vessels). HRP *Risk of Cardiovascular Adaptations*.

### Patterns that hold up

A change counts only if all four crew moved the same way the day after landing, against three different preflight
baselines (`findings/labs.txt`). Four people is a story, not proof.

| Value | Day after landing | Later | What we can say |
|---|---|---|---|
| **Glucose** | **+23%** in all 4 | Back near baseline by R+82 | The clearest flight-related change. Whether the draws were fasting is unknown, so it may reflect landing stress or meal timing |
| Bicarbonate (CO2) | -4% in all 4 | Back to baseline by R+45 | Small and within range: a transient shift in the blood's acid balance |
| Red cell size (MCV, MCH) | -3% to -4% in all 4 | Still -2% to -5% at R+194 | Within range and persistent: not attributable to a 3-day flight from this data |
| White cells / monocyte share | -20% / +26% in all 4 | Still -15% / +25% at R+194 | Persistent: more likely individual drift or season than the flight |

**What looked like a pattern and was not.** CRP (inflammation) appeared to rise 48% in all four crew. It disappears
once the L-44 draw is left out of the baseline: in the multiplex panel, L-44 reads about 10 times lower for every
crew member at once, and some values sit at the assay's ceiling. That is a lab-batch artifact, not biology. This
is why patterns are computed and stress-tested by code, and only then explained.

**Out of range worth noting.** Glucose was below the lab range (65-99 mg/dL) in 3 of 4 crew at R+45; BUN was above
range in 3 of 4 at R+194. Unexplained by the data; do not build alerts on them.

## 2. ASRS fatigue reports

**What it is.** The Aviation Safety Reporting System (run by NASA Ames) collects voluntary, anonymous reports from
pilots. NASA publishes curated sets; we use the two fatigue sets: 50 airline (FAR 121) and 50 commuter/corporate
reports, each with structured fields and the pilot's own narrative.

**Medical side.** No measurements: it is behaviour. It shows what sleep loss does in practice (the clinical picture
behind tests like the PVT-B): slower reactions, lost situational awareness, skipped steps.

**Patterns in these 100 reports** (`findings/asrs.txt`; voluntary reports describe the sample, not frequencies):
- Fatigue appears together with **lost situational awareness in 65**, workload in 45, time pressure in 39.
- **82 involve a procedural deviation**: a step done wrong or skipped. **46 happen in approach, descent or landing**.
- Narratives mention night or red-eye flights (36), duty length or hours awake (32), reserve schedules (22), and
  naps or rest as what would have helped (20). Only 2 describe falling asleep outright: the risk is degraded
  performance long before a microsleep.

## 3. Papers (aggregates, no raw data)

| Source | The numbers PULSAR uses |
|---|---|
| `jones-2022-sleep` | 24 ISS astronauts slept 6.5 h on average; under 6 h, slower reactions and more stress; under 5 h, physical complaints |
| `basner-2011-pvtb` | The 3-minute PVT-B: a reaction of 355 ms or more is a lapse |
| `flynn-evans-2016-circadian` | 21 ISS missions: 6.4 h of sleep when aligned with the body clock, 5.4 h when not |
| `trudel-2022-hemolysis` | Long missions destroy 54% more red cells; recovery takes 3-4 months |

## How PULSAR exploits it

1. **Thresholds with a real source.** Glucose out of the lab range (65-99 mg/dL, `osdr-osd-575`) can back the glucose
   rule instead of an assumption; same for potassium, sodium and calcium. A reference range is "unusual", not
   "dangerous": the team decides the escalation.
2. **Real crew replay.** A mode that plays C001-C004's real lab timeline on the body twin (metabolic, immune,
   cardiovascular systems): the demo shows real NASA astronaut data, including the R+1 glucose jump. Needs a `labs`
   block in the contract: a new goal (`new-goal`).
3. **A grounded forensic intro.** The ASRS pattern is the script: fatigue + lost situational awareness + a skipped
   procedural step during approach (docking on Mars). Narratives give the alert wording and countermeasures (rest, nap).
4. **Why the CBC matters on the way to Mars.** Space anemia grows with mission length: PULSAR's twin can show red-cell
   values as a long-mission watch item, citing `trudel-2022-hemolysis`.
5. **Rigour as a pitch point.** We tested every pattern against three baselines and threw out one that was a lab
   artifact. Judges will ask how we validated; this is the answer.

## Adding a new dataset

Use the `explain-dataset` skill: it downloads into `raw/`, computes and stress-tests patterns with code, then writes
the plain-words card here and registers the source in `shared/sources.json`.
