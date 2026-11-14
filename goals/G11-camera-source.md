# G11 · Camera source selector (optional)

Owner: FS1 · Branch: `goal/G11-camera-source` · Depends on: G1; FS3 adds an optional `deviceId` to
`frontend/src/modules/hud/useWebcam.ts` · Optional: yes (sub-goal of G1)

## Goal
The vision HUD can read any camera the OS exposes, so a robot camera (an Enabot SE mirrored from the iPhone and
published through OBS Virtual Camera) can feed the fatigue pipeline. The laptop webcam stays the default.

## Done when
- The HUD lists every video input; with no saved choice it opens the default camera.
- Choosing another camera restarts the stream on that `deviceId` and `biometrics.fatigueScore` keeps updating at
  15 fps or more, as in G1.
- The choice survives a reload.
- If the selected camera ends (OBS closed), the HUD falls back to the default within 2 s and says so on screen.
- `make check-G1` still passes.
- `docs/` records that the Enabot is an exception to the offline rule (its video goes through Enabot's cloud),
  that the team accepted it, and that the G8 demo runs without it.

## Check
`make check-G11` → `frontend/e2e/acceptance/g11-camera-source.spec.ts` (Playwright; two cameras mocked with
`page.addInitScript` over `navigator.mediaDevices`, or Chromium fake devices) and `make check-G1`.

## Out of scope
Controlling the robot, reading Enabot's stream directly (no documented local stream), `getDisplayMedia` capture.
