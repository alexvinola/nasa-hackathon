# Preparation (what an agent cannot do)

In order of urgency. Tick each box in the PR or in the team chat.

## Now, before writing code

- [ ] **RLDD download (FS1).** 111.3 GB: download only 1 fold (or 2) and start now; it is G2's critical path.
      Ask the DROZY authors if the site does not answer; YawDD needs a free IEEE account.
- [ ] **`make prefetch` on all three laptops** (MediaPipe, Piper voices, `gemma2:2b`, whisper base.en/small.en).
      Then check that it works with Wi-Fi off.
- [ ] **GitHub repo**: create `synapse-nasa-2026`, give all three access, protect `main` (PR required).
      `gh auth login` on each laptop.
- [ ] **FS1/FS2/FS3 split** decided, and each person runs `SYNAPSE_VERTICAL=FSx claude` in their clone
      (PowerShell: `$env:SYNAPSE_VERTICAL='FSx'; claude`).
- [ ] **Windows laptops**: install `make` (`scoop install make`), pnpm, Ollama, ffmpeg and gh, and run from a shell
      where Git Bash is on PATH (the `Makefile` and `scripts/*.sh` need bash). Then check that `make contract` passes.
- [ ] **Review the scenarios in `shared/scenarios/`** (FS2 + team): they are G4's criterion. If an expected
      value looks wrong, change it now, not at 3 a.m.
- [ ] **Close the open assumptions** in `docs/sources.md`: a clinical source for blood pressure, glucose and
      temperature, and NASA's cabin CO2 limit (candidate: NASA-STD-3001 Vol. 2). Add each source to
      `shared/sources.json`, cite it from the scenario and run `make sources`.

## Fixtures to record (first hour)

- [ ] `data/fixtures/eyes_closed.y4m` and `data/fixtures/alert.y4m` (10-15 s, under the venue lighting) for G1.
      `ffmpeg -i in.mp4 -pix_fmt yuv420p -r 30 out.y4m`
- [ ] 4-6 voice commands in `data/fixtures/voice/*.wav` (16 kHz mono) for G5: "how am I doing?",
      "next step", "call the flight surgeon"...

## Demo laptop

- [ ] Choose it now and measure on it: worker fps (G1) and whisper + Gemma + Piper latency running together (G5).
      The goal figures are tuned to this laptop.
- [ ] Camera and microphone permissions for the browser; "do not disturb" mode; charger.
- [ ] A watch or pulse oximeter to compare heart rate live (optional).

## Submission

- [ ] Read the Space Apps submission requirements (video, public URL, description) and the deadline.
- [ ] AWS Amplify for the static frontend in demo mode (account and permissions ready on Saturday).
- [ ] Record the full demo video on Sunday before the pitch.

## Tools

- Node 24 + pnpm, uv, Docker, gh: already installed on Alex's laptop. Ollama still needs to be started.
- Python: the system ships 3.14; pin 3.12 in `backend/` and `data/` (`uv python pin 3.12`), because
  faster-whisper (ctranslate2) and MediaPipe for Python may not have 3.14 wheels.
- Claude Code on all three laptops, with this repo: CLAUDE.md, the `work-goal` / `new-goal` skills,
  the `goal-verifier` subagent and the hooks load automatically when the project is opened.
