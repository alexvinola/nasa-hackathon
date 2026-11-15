# Demo

Space Apps accepts a demo as a deck of 7 slides or fewer (title and introduction included) or a video of 30 s or
less. Both must be in English. This folder holds one of each.

Live demo: <https://pulsar-challenge.duckdns.org/> (the HUD is at `/pulsar`). It replaces `pulsar.alexvinola.com`
in every demo material.

## Deck

`pulsar-demo.pdf`: 7 slides in English. `pulsar-demo.html` is its source: open it in Chromium and print to PDF
(1920×1080, backgrounds on).

The HUD screenshots in `img/` were taken from the live prototype with no camera; the red-state capture uses the
HUD's debug control to inject fatigue readings, as slide 5 says. Slide 1 labels the mascot render as an
AI-generated image, as the video does. Figures on slide 6 come from
`data/out/metrics.json` and `backend/bench/voice_latency.json`.

## Video (30 s)

`pulsar-demo-30s.mp4`: English captions and a procedurally synthesized soundtrack (see "Sound"). This is the
submitted demo; a silent cut of the same picture was built for comparison and is not kept.

Public link, playable in the browser with no login:
<https://cdn.jsdelivr.net/gh/alexvinola/nasa-hackathon@fef300869cdfee19a4d5a0f77105720d1212b5ee/docs/demo/pulsar-demo-30s.mp4>
(jsDelivr serves this repository's file as `video/mp4`; GitHub's own file page only offers "View raw"). Wording comes from the
[project description](../brand/PULSAR-project-description.md) and from the closing lines of the landing and the
opening film.

### Sources

- **English clips** from the team's third recording, `Grabación de pantalla 2026-11-15 a las 21.08.58.mov` (33 s,
  2908×1732; kept outside the repository): a real camera session in the English HUD where the eyes close,
  fatigue rises from green straight to red, and the reaction test is failed 2 of 3 (285 ms and 233 ms good).
- **Relaxation clip** from the team's second recording, in English, `Grabación de pantalla 2026-11-15 a las
  21.13.31.mov` (33 s, 2908×1732; kept outside the repository): the HUD with the live camera, RELAX, then the three
  guided exercises.
- **Voice logging and habits clips** from two more English recordings, `Grabación de pantalla 2026-11-15 a las
  21.23.20.mov` (15 s: "glucose 70" said into the microphone, the measurement form opens and logs it) and
  `… 21.24.02.mov` (14 s: the habits panel with level and streak, then the 30-day history). Kept outside the
  repository.
- Every clip comes from an English HUD. The first, Spanish recording (`… 12.30.33.mov`) is no longer used.
- **Stills** from the description's screenshots (`docs/brand/shots/`), for what the recordings do not show.

### Requirements

- At most 30 s, 1920×1080, 30 fps, H.264, with the synthesized soundtrack described under "Sound". The current cut is exactly 30.0 s (900 frames); if an upload
  platform reports more than 30 s, trim 0.5 s from the acronym card.
- **English on screen, end to end.** Every clip comes from the HUD in English and every caption is in English. A
  feature only recorded in Spanish is re-recorded in English, not subtitled.
- **The judge must get the problem, the solution and why it matters** (Space Apps "Presentation" criterion): the
  first scene states the problem, the middle shows PULSAR solving it, the last says why it matters.
- **Sleep first.** PULSAR today specialises in the risk of sleep loss and fatigue (NASA HRP: Performance
  Decrements and Adverse Health Outcomes Resulting from Sleep Loss, Circadian Desynchronization, and Work
  Overload). Captions and source lines frame monitoring, alerts, the reaction test and habits around that risk.
- **Motion first.** Wherever a recording shows a feature, the scene is a clip of it at real speed (no speed-ups),
  so the video shows a working product and not only pictures. Stills only for the logo; the acronym is a text card.
- **Real sessions, labelled honestly.** Fatigue, eye closure and the alert come from a real camera session; if a
  value were forced with the HUD's debug keys, the scene would say "simulated readings".
- **Commercial tone.** Each caption sells one benefit in a few words: a short kicker and one line. No section
  labels such as "What the name means".
- **True to the product.** A caption never claims what PULSAR does not do. The AI estimates fatigue and phrases
  the answer, but explicit rules decide every status and escalation (`CLAUDE.md`, product rules), and decisions use
  the current readings, not the history. A red fatigue alarm stops only by passing the reaction test or by
  choosing to go and rest; it does not lock the astronaut out of their work.
- **Technical credibility.** Several scenes carry a short source line with a figure from an official NASA study,
  standard or database, in small mono type under the caption. Every figure traces to `shared/sources.json`; none is
  rounded up or generalised beyond what the source says.
- **It opens on the problem**, before the logo: the landing's line "On a long mission, nobody looks at your face
  every morning", over the English recording of the eyes closing, blurred and darkened. As a blurred backdrop
  with no HUD legible, it may fill the frame; it is the one exception to "never crop".
- **Then the logo and the acronym:** at most 8.5 s together. First the logo (`live-02-intro`) with NASA Space Apps
  2026 and the team, then the acronym: each letter of P.U.L.S.A.R. with what it stands for and the sentence the
  description gives it, word for word, with no title above it.
- **Never crop a screenshot or a clip.** Each one is shown whole, scaled to fit the frame with margins, so the side
  panels stay visible. Any zoom stays inside those margins.
- Captions sit under the picture, not over it, and fit on one line each; only the problem scene, a full-frame
  text scene, uses a two-line headline.
- **AI label on the logo only.** The mascot render in the logo scene is AI-generated: that scene carries a small
  "AI-generated image" label in the bottom-right corner. The other scenes are screen captures and carry no label.
- **The reaction self-test has its own scene:** when fatigue goes red, the alarm stops only by passing it or by
  choosing to rest.
- **Measuring is multimodal and taught:** the measurement scene shows a value said by voice, the form logging it
  and the step-by-step guide on the 3D body, and says that the guides follow NIH MedlinePlus and CDC.
- **Gamification has its own scene:** XP, levels, streaks and badges to build good habits.
- **It ends on the mission, not on a feature:** the last scene carries the message that caring for the crew's
  health is what gets the mission done, over the slow-breathing exercise in motion, with the live demo URL. The
  clip starts inside the exercise, not on the face or the menu.
- Any URL shown on screen is the live demo, `pulsar-challenge.duckdns.org`.
- Any scene whose values are simulated or sample data says so on screen.
- **Nothing is uploaded until the team validates it.** The video, like every demo material, stays local until a
  team member approves it; then it gets a public link that needs no login.

### Storyboard

30.0 s, exactly the limit: nine scenes with 0.5 s crossfades. "EN rec" times are seconds into the English recording
named in each row. The source line is a third, smaller line under the caption.

| # | Time | Picture | Kicker | Caption | Source line |
|---|---|---|---|---|---|
| 1 | 3.5 s | Clip, EN rec 21.08.58 at 2.5–6 (eyes closing), blurred and darkened | The problem | On a long mission, nobody looks at your face every morning. · Fatigue gives no warning: it shows in the eyes before it shows in the mistakes. | Sleep loss is an official NASA HRP risk · ISS astronauts reported sleeping 6.5 h on average (Jones et al. 2022). |
| 2 | 2.5 s | Still `live-02-intro` + AI label | NASA Space Apps 2026 | The team | |
| 3 | 6 s | Text card | (none) | The six rows of the acronym table in the description, word for word | |
| 4 | 4 s | Clip, EN rec 21.08.58 at 1.5–5.5 (eyes close, fatigue rises) | Always-on active monitoring · live recording | The webcam spots sleep-loss fatigue live: eye closure, blinks, yawns. | Sleep loss is an official NASA HRP risk · under 6 h of sleep, ISS astronauts reacted slower (Jones et al. 2022). |
| 5 | 4 s | Clip, EN rec 21.08.58 at 5.5–9.5 (green turns red) | Smart alerts you can trust | AI reads the signals, clear rules decide: RED, call the flight surgeon. | In 65 of 100 NASA ASRS fatigue reports, crews also lost situational awareness. |
| 6 | 3.5 s | Clip, EN rec 21.08.58 at 18.7–22.2 (NOW, 233 ms, test failed 2/3) | Reaction self-test (PVT-B) | Pass the test or go rest: a red alarm can't be ignored. | The PVT-B of NASA's Reaction Self Test on the ISS (Jones et al. 2022, 24 astronauts) · 355 ms lapse (Basner et al. 2011). |
| 7 | 4 s | Clip, EN rec 21.23.20 at 4.5–8.5 ("glucose 70" said, form opens, logged) | Talk, type or tap | Say "glucose 70": logged, with a 3D guide to measure it right. | Step-by-step guides based on NIH MedlinePlus and CDC instructions. |
| 8 | 3 s | Clip, EN rec 21.24.02 at 4.5–7.5 (habits panel, history opens) | Gamification · sample history | XP, levels, streaks and badges turn good habits into a game. | 8.5 h sleep target: the sleep period NASA-STD-3001 recommends. |
| 9 | 3.5 s | Clip, EN rec 21.13.31 at 3–6.5 (slow breathing, inhale) | The human side of the mission | Caring for the crew is caring for the mission. | Try it: pulsar-challenge.duckdns.org |

Symptoms and the all-green closing still are left out: sleep comes first and the 30 s do not allow them.

Source lines trace to `shared/sources.json`: NASA ASRS Database Report Sets (the counts describe that sample of
voluntary reports, not how often anything happens), NASA HRP Risks of Human Spaceflight, Jones et al. (2022) in
*Sleep*, Basner, Mollicone & Dinges (2011) in *Acta Astronautica*, the NIH MedlinePlus and CDC measurement guides,
and NASA-STD-3001 Volume 1 Rev. C, section 6.1.
"Caring for the crew is caring for the mission" and "The human side of the mission" come from the landing
(`pulsar-landing.html`) and the opening film (`pulsar-intro.html`).

### Look and build

- Brand palette and type of `docs/brand/README.md`: space-navy background, kicker in JetBrains Mono (pulse cyan,
  uppercase), caption in Manrope bold with the key phrase in cyan, source line in small mono after a lilac "▸",
  notes such as "sample history" in amber next to the kicker.
- Clips are scaled whole into a 1363×812 frame at the top centre (x 278, y 36) with a thin border; captions fill
  the band below. Stills get a slow zoom of at most 1.2 %, inside the margins.
- Captions are HTML rendered to transparent PNGs with Playwright and laid over the picture with ffmpeg: each fades
  in over 0.4 s; scenes are joined with 0.5 s crossfades; the video fades in over 0.3 s and out over 0.7 s. H.264,
  CRF 20, `+faststart`.
- Checks before handing it over: duration with `ffprobe` (at most 30.0 s), one frame per second reviewed as a
  contact sheet, and no caption wider than the frame (right edge at most 1820 px).

### Sound

`pulsar-demo-30s.mp4` carries a soundtrack synthesized in Python (numpy), with no recorded or licensed
music, synced to the scenes: a slow heartbeat under the problem (the "pulse" of PULSAR), a bell sting on the logo,
the heartbeat again and speeding up while fatigue rises, a two-tone alarm when the HUD turns red, a blip on the
reaction test's NOW, a falling tone on "Test failed", a chime on "Logged", a sparkle when the history opens, and a
warm chord with a soft breath on the closing. An airy A-major pad runs underneath and ducks under the alarm.
Loudness normalised to -16 LUFS, true peak -1.5 dBTP, AAC 192 kb/s.

Space Apps asks that generated audio be acknowledged in descriptive text and in metadata: the file's `comment`
tag says the soundtrack was synthesized with AI-assisted code, and the submission's "Use of AI" field must say the
same.

## Pending

- Put the video's public link (above) in the submission, and say in its "Use of AI" field that the soundtrack was
  synthesized with AI-assisted code.
