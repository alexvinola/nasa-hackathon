# Preparation (what an agent cannot do)

In order of urgency. Tick each box only with current evidence in the PR or team chat.
Some source and fixtures now exist; unchecked items are readiness checks, not statements
that all implementation is missing. See [implementation status](IMPLEMENTATION.md)
and [the agent harness](HARNESS.md).

## Now, before writing code

- [ ] **RLDD download (FS1).** 111.3 GB: download only 1 fold (or 2) and start now; it is G2's critical path.
      Ask the DROZY authors if the site does not answer; YawDD needs a free IEEE account.
- [ ] **`make prefetch` on all three laptops** (MediaPipe, Piper voices, `gemma4:e4b-it-qat` (6.1 GB), whisper base.en/small.en). Gemma 4 needs a current Ollama: the model requires 0.30.5 or later (0.22.1 fails the pull with a 412 error), so run
      `brew upgrade ollama` first (0.40.16 on Alex's laptop); prefetch stops with an error otherwise. Under 16 GB of RAM:
      `PULSAR_LLM_MODEL=gemma4:e2b-it-qat make prefetch`, and start the backend with the same variable.
      Then check that it works with Wi-Fi off.
- [ ] **GitHub repo**: confirm all three have access to `alexvinola/nasa-hackathon` and protect `main` (PR required).
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
- [ ] Verify the existing voice fixtures and record any missing commands in `data/fixtures/voice/*.wav`
      (16 kHz mono) for G5: "how am I doing?",
      "next step", "call the flight surgeon"...

## Demo laptop

- [ ] Choose it now and measure on it: worker fps (G1) and whisper + Gemma + Piper latency running together (G5).
      The goal figures are tuned to this laptop.
- [ ] Camera and microphone permissions for the browser; "do not disturb" mode; charger.
- [ ] A watch or pulse oximeter to compare heart rate live (optional).

## Submission

- [ ] Read the Space Apps submission requirements (video, public URL, description) and the deadline.
- [ ] If a public static presentation is required, agree its hosting separately. It must not receive
      health data or become a runtime dependency of the offline demo.
- [ ] Record the full demo video on Sunday before the pitch.

## Tools

- Node 24 + pnpm, uv, Docker, gh: already installed on Alex's laptop. Ollama still needs to be started.
- Python: the system ships 3.14; pin 3.12 in `backend/` and `data/` (`uv python pin 3.12`), because
  faster-whisper (ctranslate2) and MediaPipe for Python may not have 3.14 wheels.
- Verify customization discovery on each host: Claude Code uses CLAUDE.md and `.claude/`;
  VS Code uses AGENTS.md and the repository `.github/agents/` wrappers and harness skill.
  Existing workflows remain in `.claude/skills/`. Check the active hooks rather than assuming
  that every editor/tool enforces them. See [the harness guide](HARNESS.md).
