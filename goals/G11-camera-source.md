# G11 · Video source selector (optional)

Owner: FS1 · Branch: `goal/G11-camera-source` · Depends on: G1; it changes `frontend/src/modules/hud/` (`useWebcam.ts`,
`Hud.tsx`), which is FS3's: agree the change with FS3 · Optional: yes (sub-goal of G1)

## Goal
The vision HUD can read a video source other than the laptop webcam, so a robot camera can feed the fatigue pipeline:
an Enabot SE mirrored from the iPhone, either through OBS Virtual Camera (an OS camera) or by sharing its window
(`getDisplayMedia`). The laptop webcam stays the default.

## Done when
- With no saved choice the HUD opens the default camera.
- The HUD offers every video input and a "Share screen" option; one source is live at a time.
- Choosing another camera or a shared window restarts the stream on it, and `biometrics.fatigueScore` keeps updating
  at 15 fps or more from that source, as in G1. A shared window feeds the pipeline like a camera does.
- The screen-share request leaves PULSAR's own tab out (`selfBrowserSurface: "exclude"`), so the HUD never films itself.
- A chosen camera survives a reload. A shared window cannot be reopened without a click, so after a reload the HUD
  opens the default camera and says sharing has to be started again.
- If the source ends (OBS closed, sharing stopped from the browser), the HUD falls back to the default camera within
  2 s and says so on screen.
- A shared window is handled like the webcam: frames stay in the browser, nothing is stored or sent.
- `make check-G1` still passes.
- `docs/` records that the Enabot is an exception to the offline rule (its video goes through Enabot's cloud),
  that the team accepted it, and that the G8 demo runs without it.

## Check
`make check-G11` → `frontend/e2e/acceptance/g11-camera-source.spec.ts` (Playwright; two cameras and a screen share
mocked with `page.addInitScript` over `navigator.mediaDevices`, or Chromium fake devices) and `make check-G1`.

## Out of scope
Controlling the robot, reading Enabot's stream directly (no documented local stream), recording the shared screen.

## Changes
- 2026-11-14: screen sharing (`getDisplayMedia`) moved from out of scope to an allowed source, as a second way to
  bring in the mirrored iPhone without OBS. The shared window must feed the fatigue pipeline and fall back like a
  camera.
