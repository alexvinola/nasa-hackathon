# Judging rubric and where PULSAR stands

Snapshot: 2026-11-15, 04:30 CET, on commit `7cf2df9`. The rubric and the submission rules are quoted from the official 2026 guides
(links at the end). The assessment lists repository evidence for and against each criterion; it assigns
no scores. See [implementation status](IMPLEMENTATION.md) for goal-by-goal evidence.

**Deadline: Sunday, November 15, 2026 at 11:59 p.m., local time of the team's Local Event.**
Anything saved or submitted later is not judged.

## The rubric, as published

"At every level of judging, from Local and Universal Events to Executive Judging, your project will be
evaluated on a scale of 1-to-5, in each of the following criteria." The guide gives no weights, and it
describes only the top score of each criterion.

### Impact

> This project makes an impact by addressing either a minor or major problem, which influences the quality and
> quantity of its overall effect. The extent to which it inspires or helps others varies, ranging from a broad
> audience to a select few.
>
> **Score of 5 (Outstanding Impact):** This project demonstrates exceptional impact, addressing a significant
> problem with proposed solutions. Its reach is extensive, inspiring, benefits a large audience, or could change
> the world. The quality and effectiveness of the project far exceeds expectations, setting a high standard for
> others.

### Creativity

> This project demonstrates originality and innovation. It introduces a novel concept that has not been attempted
> before or presents an improvement upon existing ideas in a meaningful way. This project is distinguished by its
> level of creativity, showcasing a fresh perspective or inventive execution.
>
> **Score of 5 (Highly Creative and Innovative):** This project showcases remarkable creativity, introducing a
> groundbreaking approach that has never been attempted before. It challenges conventional methods, presenting an
> original and inventive proposed solution that stands out in its field. The uniqueness of the idea makes it a
> true innovation.

### Validity

> This project presents a proposed solution that is grounded in scientific principles and demonstrates technical,
> functional, or logical feasibility. It is designed to effectively achieve its intended purpose and has the
> potential to function in real-world applications. The completeness of the proposed solution varies—it may be
> fully developed or still require significant refinement. Additionally, the usability and user-friendliness of
> the project influence its practicality and accessibility.
>
> **Score of 5 (Highly Valid and Feasible):** This proposed solution is scientifically sound and technically
> feasible, demonstrating strong alignment with established principles. It is fully developed and ready for
> real-world implementation, effectively achieving its intended purpose. The project is highly usable and
> user-friendly, making it accessible and practical for widespread application.

### Relevance

> This project fully and directly addresses the challenge for which it was submitted, demonstrating a strong
> alignment with the intended objectives. It meaningfully integrates NASA data, utilizing it as a core component
> of the proposed solution rather than a superficial addition. The depth of engagement with the data enhances the
> project's credibility and effectiveness.
>
> **Score of 5 (Highly Relevant and Strong NASA Data Integration):** This project thoroughly engages with the
> challenge, delivering a proposed solution that is deeply connected to the intended goals. NASA data is integral
> to the project's success, providing meaningful insights that drive the innovation forward. The use of data is
> well-executed, enhancing both the credibility and impact of the solution.

### Presentation

> The team effectively communicated their project, clearly conveying the challenge, their proposed solution, and
> its significance. The storytelling was engaging and well-structured, ensuring the audience understood the
> project's purpose and impact. The clarity, organization, and delivery of their presentation played a key role
> in making their ideas compelling and clear. Judges evaluate the demo and full project to compute this score.
>
> **Score of 5 (Exceptional Communication and Storytelling):** The team delivered a well-structured and
> compelling presentation, clearly articulating the challenge, proposed solution, and importance of the project.
> Their storytelling was engaging, allowing the audience to fully grasp the significance and potential impact of
> the work. The delivery was polished, structured, and highly effective in communicating their ideas.

The guide asks teams to "pay equal attention to the final criterion: presentation". The submission guide adds
that the demo counts, "but the majority of judges' evaluation will be based on your project submission": the
project page is what gets scored.

### Phases and awards

| Phase | Who judges | Announced |
|---|---|---|
| 1. Local judging, Global Nominees | Local judges, with this same rubric | 2026-12-03 |
| 2. Global Finalists and Honorable Mentions | Expert judges, with this same rubric | 2026-12-17 |
| 3. Global Winners | Executives from NASA and the partner space agencies | 2027-01-26 |

Ten global awards: Best Use of Science, Best Use of Data, Best Use of Technology, Galactic Impact,
Best Mission Concept, Most Inspirational, Best Storytelling, Global Connection, Art & Technology and Local Impact.
Local Leads may also give local awards, separate from the global ones.

## Eligibility: pass or fail

A project that misses any of these is not judged globally, whatever its score.

| Requirement | Status on 2026-11-15 |
|---|---|
| Submitted before the deadline, with every required field filled in | Not done yet |
| Demo is a video of 30 s or less, or a deck of 7 slides or fewer (title and intro included). Over the limit means not eligible for Global Judging | **Not met.** The opening film in `docs/brand/pulsar-intro.html` runs 41 s and the full pitch 2:45 |
| Demo and final project links open with no login, permission or registration | **Not met.** `alexvinola/nasa-hackathon` is private and the presentation's GitHub Pages is disabled |
| English on the project page and in every linked material. A video may be spoken in another language only with English subtitles; slides must be in English | The repository is in English. The pitch page and the HUD default to Spanish: link the pitch with `?lang=en` and subtitle any Spanish video |
| At least one NASA data set or resource, described in the NASA Data field (needed for a Global Award) | Met: HRP hazards and risks, OSDR OSD-569 and OSD-575, ASRS report sets, NASA-STD-3001 (`shared/sources.json`) |
| Every external resource listed in References: code, text, images, data, even if open source | To write. Include RLDD, DROZY, YawDD, MRL Eye, MediaPipe, Gemma, Whisper, Piper and three.js |
| AI use declared. Generated images and video carry a visible watermark; generated audio, code and data are acknowledged in descriptive text and metadata; no NASA logos or mission identifiers in generated content | To write. Open question: if the mascot render is AI-generated it needs a visible watermark |
| No image, video, audio or likeness of anyone under 18 | Check the demo footage |
| One to six members, all registered at the same Local Event and listed on the team page | Check on the team page |
| Both boxes ticked: terms and conditions, and original work | At submission |

## PULSAR against the rubric

| Criterion | In favour | Against |
|---|---|---|
| Impact | Crew medical autonomy on long missions, a problem the HRP names | A prototype with no validation; a 5 asks for broad reach |
| Creativity | Camera fatigue, PVT-B and deterministic rules; the LLM only phrases the verdict; everything runs offline | Each piece exists elsewhere; the combination is what is new |
| Validity | Every figure has a source or is declared as an assumption; contract and rules checks pass | Weak fatigue model; 6 of 8 rules use a placeholder threshold; 19 open assumptions |
| Relevance | All six indicators the challenge names, with guides, a clickable body, colour coding and escalation to the flight surgeon; habits with reminders, charts over time, streaks and badges | The charts cover habits, not the measured indicators, and start on demo data; no mission environments; real NASA data does not reach the product |
| Presentation | Opening film, mascot and bilingual pitch already exist | No demo within the format limits and no project page yet |

### Evidence behind the assessment

- **Validity.** The shipped fatigue model has macro-F1 0.43 and AUC 0.62, and a Spearman correlation of 0.32
  with PVT reaction time on DROZY (`data/out/metrics.json`). Present it as an indicative signal, not a detector.
  Of the eight rules in `backend/assets/rules.json`, only `perclos-high` and `sleep-under-6h` cite a source for
  their threshold. The 19 unsourced claims are listed under "Open assumptions" in [sources](sources.md).
- **Relevance.** The challenge names heart rate, blood pressure, blood glucose, body temperature, sleep and mood;
  `shared/indicators.json` covers all six. The HRP vocabulary is a core component (`shared/hrp.json`, the health
  points on the body). The Inspiration4 labs and the ASRS reports are analysed in `research/nasa-data/`, but
  inside `frontend/`, `backend/` and `shared/` they appear only as entries in `shared/sources.json`.
  From the challenge's optional list, the habits panel (`frontend/src/modules/habits`) covers three items:
  prompts when a habit is due, gamification (XP, levels, streaks and badges) and bars per day over 3, 7 or 30
  days. Two limits: the charts show the four habits (sleep, exercise, water, relaxation), not the readings of
  heart rate, blood pressure, glucose, temperature or mood; and until the user has a past day of their own the
  history is 60 days of demo data, not measurements. The habit targets are team assumptions.
  Not built: different mission environments.
- **Checks run on 2026-11-15, on `7cf2df9`.** `make contract` (7 valid, 0 failures), `make check-G3` (26 tests
  passed), `make check-G4` (6 scenarios passed) and the habits unit tests (8 passed). Not run here: G1, G2, G5,
  G8 and G9. Acceptance tests are missing for G0 (frontend), G6, G7, G10 and G12, and the G1 video fixtures are
  absent on the laptop used.

## How to work the gaps

About 19 hours were left at the snapshot. The order below follows what costs the most if it is missed:
eligibility first, then the page the judges score, then product changes.

### Working rules for today

- **Submit early, then improve.** The page can be edited and resubmitted until the deadline and only the last
  saved version is judged. Get a complete, eligible submission in first; every later step only raises the score.
- **Record before changing.** Capture demo footage of what works now, before any code change, so a broken build
  late in the day cannot cost the demo.
- **Submission work needs no goal.** The video, the links and the page text are not code: tick them in the
  Submission list of [PREP](PREP.md).
- **Product changes stay goal-driven.** A new behaviour gets a goal with the `new-goal` skill, an acceptance test
  the human approves, and its own branch with `work-goal`. `shared/**`, `goals/**` and `**/acceptance/**` are
  protected (`goals/protected.txt`): editing them needs a human yes.
- **A new source goes through the registry.** Add it to `shared/sources.json`, cite it from the rule or the
  scenario, then run `make contract` and `make sources`.
- **No threshold changes to look better.** A rule's threshold changes the expected result of the G4 scenarios.
  Without a source, keep the placeholder and say it is one.
- **Set a code freeze** a few hours before the deadline and spend the rest on the page and a Wi-Fi-off rehearsal.

### Step 1. Make the submission eligible (everyone)

| Task | How | Owner |
|---|---|---|
| Demo within the limit | Cut a video of 30 s or less from the opening film and a HUD screen recording, with English subtitles; or build 7 slides in English. Storyboard below | FS3 |
| Public links | Decide what becomes public: this repository, the presentation's Pages site, or both. Open each link in a private window to confirm it needs no login | Repository owner |
| English entry point | Link the pitch with `?lang=en`; record the HUD in English | FS3 |
| AI watermark | Confirm how the mascot was made; if generated, add a visible watermark wherever it appears | FS3 |
| First submission | Fill in every field of the project page, tick both boxes, press "Submit for Judging" | Team owner |

### Step 2. Presentation: the project page and the demo

The page is the main thing the judges read, so write it for someone with no context. Each field already has its
material in the repository:

| Page field | Take it from |
|---|---|
| High-level summary | [README](../README.md) and the tagline in `docs/brand/README.md`: what it is, how it answers the challenge, why it matters |
| Detailed description | The chain "vision measures, the classifier estimates, the rules engine decides, Gemma only phrases"; the stack in `CLAUDE.md`; the limits (not a medical device) |
| NASA Data | The `nasa.gov` entries of `shared/sources.json`, each with what PULSAR takes from it ([sources](sources.md)) |
| Partner data and references | CSA pages, the papers, the datasets (RLDD, DROZY, YawDD, MRL Eye) and the libraries and models |
| Use of AI | Code written with AI assistants; Gemma phrases the verdict at runtime; Piper synthesises the voice; Whisper transcribes |

Storyboard for the 30-second video, following the timing the submission guide suggests:

| Time | Content |
|---|---|
| 0:00 | Team name and members |
| 0:02 | The challenge: on long missions astronauts must spot health changes themselves |
| 0:05 | "PULSAR, your personal health companion in space" |
| 0:10 | The HUD working: the camera reads fatigue, an indicator turns amber, the guide opens on the body, the rules engine escalates to the flight surgeon. One caption: built on NASA's HRP hazards and risks |
| 0:20 | The future: runs on one laptop with no network, for a station, a lunar base or a Mars transit |

### Step 3. Relevance: bring NASA data into the product

| Task | How | Owner |
|---|---|---|
| Inspiration4 reference ranges in a guide | Show, in the glucose guide, the range the lab used for the Inspiration4 crew (65 to 99 mg/dL, `research/nasa-data/findings/labs.txt`), cited as `osdr-osd-569`. Label it as that lab's reference range, not a PULSAR threshold: G9 forbids invented ranges. New goal, since `shared/indicators.json` is protected | FS3 |
| Chart a measured indicator | The habits panel already charts days; the measurement form keeps no history. Store each reading locally and chart one indicator (heart rate or glucose) the same way, the challenge's "how astronaut's health indicators change over time" | FS3 |
| Label the demo history | The 60 days of habit history are demo data. Say so in the video and on the page, or record with real entries only | FS3 |
| Say it on the page | Explain that the ASRS reports shaped the intro and the alert wording, and that the HRP names drive the body points and every rule's risk | FS2 |

Mission environments are optional in the challenge. Leave them out rather than ship them half done.

### Step 4. Validity: fewer placeholders, more measured evidence

| Task | How | Owner |
|---|---|---|
| Source the cabin CO2 limit | The candidate noted in the repository is NASA-STD-3001 Vol. 2. Read the figure in the standard, register the source and cite it from `cabin-co2-high` and the scenarios. If the figure differs from 4.0 mmHg, the scenario change needs `new-goal` | FS2 |
| Run what was not run | `make check-G5`, `make check-G8`, `make check-G9`, and one rehearsal with Wi-Fi off. Write the results in [implementation status](IMPLEMENTATION.md) | Everyone |
| Quote only what is demonstrated | Use the sentences under "What can be said" in `data/out/fatigue_report.md`. The same report shows the model's score runs in a narrow band, so the 0.70 placeholder of `fatigue-score-high` does not carry over from the old formula: say so, or recalibrate it through a goal | FS1 |
| State the limits | Put the 19 open assumptions and "not a medical device" on the page. A declared assumption reads as rigour; a hidden one reads as an error | FS2 |

### Step 5. Impact and Creativity: these are won in the text

- **Impact.** Name who benefits and why now: crews beyond real-time contact with flight surgeons. Add the use on
  Earth as a stated possibility (isolated or offline settings), without figures nobody measured.
- **Creativity.** Lead with the design decision that sets PULSAR apart: the LLM never decides a status or an
  escalation, and nothing leaves the laptop. Show it in the demo rather than only writing it.

### If time runs out

Cut from the bottom: step 5 polish, then step 4's CO2 source, then step 3's indicator chart. Steps 1 and 2 are
not optional.

## Sources

- [Judging & Awards Guide 2026](https://www.spaceappschallenge.org/resources/judging-awards-guide/) (dated 2026-11-13)
- [Project Submission Guide 2026](https://www.spaceappschallenge.org/resources/project-submission-guide/)
- [Challenge: Create Health Monitoring Software for Astronauts on Space Missions](https://www.spaceappschallenge.org/2026/challenges/health-monitoring-software/)
