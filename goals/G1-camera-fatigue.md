# G1 · Camera-based fatigue

Owner: FS1 · Branch: `goal/G1-camera-fatigue` · Depends on: G0, G2 (can start with fixed thresholds)

## Goal
MediaPipe Face + Pose in a Web Worker computes PERCLOS, yawns, head nods and arm asymmetry, and writes `fatigueScore` to the store.

## Done when
- With `data/fixtures/eyes_closed.y4m` as the webcam, `biometrics.fatigueScore` exceeds 0.7 in under 5 s.
- With `data/fixtures/alert.y4m`, it stays below 0.4 for 10 s.
- The worker runs at 15 fps or more on the demo laptop (the test measures and prints it).

## Check
`make check-G1` → `frontend/e2e/acceptance/g1-fatigue.spec.ts` (Playwright with Chromium and `--use-fake-device-for-media-stream --use-file-for-fake-video-capture=<y4m>`). The store is exposed as `window.__synapse` in test mode only, so the test can read it.

## First step
Record the two fixture videos (10-15 s, same lighting as the venue) and convert them: `ffmpeg -i in.mp4 -pix_fmt yuv420p -r 30 eyes_closed.y4m`. Write the test, have the owner approve it, then lock it.

## Out of scope
rPPG (stretch), camera-based HRV (cut).
