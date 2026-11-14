# DROZY face probe

Can MediaPipe Face Landmarker (the browser's `face_landmarker.task`, `mediapipe` 1.2.3 in Python and
`@mediapipe/tasks-vision` ^1.2.3 in the frontend) find the face and follow the eyelids in DROZY's videos? Run before
G2 builds its extractor on them. Script and commands: `drozy_face.py`.

DROZY: Massoz, Langohr, François & Verly (2016), *The ULg Multimodality Drowsiness Database (called DROZY) and
Examples of Use*, WACV 2016 (`drozy` in `shared/sources.json`). The script prints numbers only; no frame is saved,
shown or committed, as the license requires.

## Results (2026-11-14, one MacBook, CPU)

DROZY's video is Kinect v2 near-infrared, 8-bit grayscale, 512x424; the face is small, about 62-68 px wide.

**Face found, frames one by one (IMAGE mode, 120 frames spread over each of the 36 videos):** median 85%, but 20 videos
under 90% and some almost never (1-3: 6%, 3-2: 4%, 4-2: 15%). Mostly the 15 fps tests, which DROZY recorded in the dark.

**Face found, as the browser runs it (VIDEO mode, 8 stretches of 90 consecutive frames):**

| Test | IMAGE | VIDEO |
|---|---|---|
| 1-3 | 6% | 82% |
| 3-2 | 4% | 98% |
| 4-2 | 15% | 100% |
| 6-3 | 7% | 74% |
| 14-2 | 28% | 100% |
| 14-3 | 29% | 100% |
| 10-1 | 54% | 100% |
| 2-1 | 100% | 100% |

Tracking keeps the face once it has been found; finding it from scratch is the hard part. Brightness does not explain
the misses (2-1 and 14-2 have the same mean brightness), and contrast fixes (CLAHE, gamma 0.5, both) made detection
worse, not better. Face size, position and the nose/chin ratio from DROZY's landmarks are the same in found and missed
frames, so the likely cause is the small near-infrared face, not head pose.

**Eyelids, when the face is found (IMAGE mode, against the EAR from DROZY's automatic 68-point landmarks):**

- MediaPipe EAR vs DROZY EAR: median r = +0.75 (range +0.22 to +0.96).
- `eyeBlink` blendshapes vs DROZY EAR: median r = -0.75 (`eyeBlink` rises as the eye closes).
- DROZY's landmarks are automatic too: this measures agreement between two trackers, not accuracy.
- Mean `eyeBlink` per test ranges from 0.03 to 0.23: a fixed 0.5 threshold would rarely fire for some people.

The detect times the script prints are this machine's CPU on 512x424 frames: not the demo's fps.

## What it means for G2

1. Extract features in VIDEO mode over consecutive frames, as the browser does (also what G2's "same extractor"
   requires). Frames one by one lose most of the 15 fps tests.
2. Drop windows where the face is missing (for example under 80% of the frames in a 60 s window): a lost face must not
   read as drowsiness.
3. Per-subject calibration is required, not optional: the open-eye `eyeBlink` level differs a lot between people.
4. Near-infrared, small faces: DROZY numbers do not transfer to the colour webcam of the demo. Use it to validate
   against the PVT; train on RLDD.
