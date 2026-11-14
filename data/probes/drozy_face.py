"""Does MediaPipe Face Landmarker find the face and follow the eyelids in DROZY's near-infrared videos?

Prints numbers only: no frame is saved, shown or sent anywhere (DROZY license, `drozy` in shared/sources.json).
Results and how to read them: data/probes/README.md.

From the repository root (data/pyproject.toml does not exist until G2):
  uv run --no-project --python 3.12 --with mediapipe --with opencv-python-headless \
    python data/probes/drozy_face.py image                 # every video, frames one by one
  uv run ... python data/probes/drozy_face.py video 1-3 3-2  # the browser's mode, on stretches of consecutive frames
"""

import argparse
import time
from pathlib import Path

import cv2
import mediapipe as mp
import numpy as np
from mediapipe.tasks.python import BaseOptions
from mediapipe.tasks.python.vision import FaceLandmarker, FaceLandmarkerOptions, RunningMode

ROOT = Path(__file__).resolve().parents[2]
DROZY = ROOT / "data" / "raw" / "drozy" / "DROZY"
MODEL = ROOT / "frontend" / "public" / "mediapipe" / "face_landmarker.task"  # the browser's model, so both agree

# Eye landmarks for the EAR (soukupova-2016-ear): MediaPipe's 478-point mesh, and the 68-point scheme of DROZY's
# automatic annotations
MP_EYES = [(33, 160, 158, 133, 153, 144), (362, 385, 387, 263, 373, 380)]
D68_EYES = [(36, 37, 38, 39, 40, 41), (42, 43, 44, 45, 46, 47)]


def ear(points: np.ndarray, idx: tuple[int, ...]) -> float:
    p1, p2, p3, p4, p5, p6 = (points[i] for i in idx)
    return (np.linalg.norm(p2 - p6) + np.linalg.norm(p3 - p5)) / (2 * np.linalg.norm(p1 - p4))


def corr(a: list[float], b: list[float]) -> float:
    a, b = np.asarray(a), np.asarray(b)
    return float(np.corrcoef(a, b)[0, 1]) if len(a) > 5 and a.std() > 0 and b.std() > 0 else float("nan")


def landmarker(mode: RunningMode) -> FaceLandmarker:
    return FaceLandmarker.create_from_options(FaceLandmarkerOptions(
        base_options=BaseOptions(model_asset_path=str(MODEL)), running_mode=mode, num_faces=1,
        output_face_blendshapes=True))


def videos(names: list[str]) -> list[Path]:
    paths = sorted((DROZY / "videos_i8").glob("*.mp4"), key=lambda p: [int(x) for x in p.stem.split("-")])
    return [p for p in paths if not names or p.stem in names]


def annotations(name: str) -> np.ndarray:
    return np.loadtxt(DROZY / "annotations-auto" / f"{name}-s2.txt")


def rgb(frame: np.ndarray) -> mp.Image:
    return mp.Image(image_format=mp.ImageFormat.SRGB, data=cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))


def image_mode(names: list[str], samples: int) -> None:
    """Frames spread over each video, one by one: face found, and eyelids against DROZY's own landmarks."""
    rows = []
    with landmarker(RunningMode.IMAGE) as model:
        for video in videos(names):
            cap = cv2.VideoCapture(str(video))
            total, fps = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)), cap.get(cv2.CAP_PROP_FPS)
            annot = annotations(video.stem)
            found, mp_ear, d_ear, blink, ms = 0, [], [], [], []
            for index in np.linspace(0, total - 1, samples).astype(int):
                cap.set(cv2.CAP_PROP_POS_FRAMES, int(index))
                ok, frame = cap.read()
                if not ok:
                    continue
                started = time.perf_counter()
                result = model.detect(rgb(frame))
                ms.append((time.perf_counter() - started) * 1000)
                if not result.face_landmarks:
                    continue
                found += 1
                h, w = frame.shape[:2]
                points = np.array([(lm.x * w, lm.y * h) for lm in result.face_landmarks[0]])
                scores = {c.category_name: c.score for c in result.face_blendshapes[0]}
                if index < len(annot) and annot[index].any():
                    mp_ear.append(np.mean([ear(points, idx) for idx in MP_EYES]))
                    d_ear.append(np.mean([ear(annot[index].reshape(68, 2), idx) for idx in D68_EYES]))
                    blink.append((scores["eyeBlinkLeft"] + scores["eyeBlinkRight"]) / 2)
            cap.release()
            row = (video.stem, fps, found / samples, corr(mp_ear, d_ear), corr(blink, d_ear),
                   float(np.mean(blink)) if blink else float("nan"), float(np.median(ms)))
            rows.append(row)
            print(f"{row[0]:>5}  fps {row[1]:4.1f}  face {row[2]:5.0%}  r(EAR mp,drozy) {row[3]:+.2f}  "
                  f"r(eyeBlink,drozy EAR) {row[4]:+.2f}  mean eyeBlink {row[5]:.2f}", flush=True)

    face, r_ear, r_blink = (np.array([r[i] for r in rows]) for i in (2, 3, 4))
    print(f"\n{len(rows)} videos, {samples} frames each, IMAGE mode")
    print(f"face found: median {np.median(face):.0%}, min {face.min():.0%}, videos under 90%: {(face < 0.9).sum()}")
    print(f"r(MediaPipe EAR, DROZY EAR): median {np.nanmedian(r_ear):+.2f}, min {np.nanmin(r_ear):+.2f}")
    print(f"r(eyeBlink, DROZY EAR): median {np.nanmedian(r_blink):+.2f} (negative: eyeBlink rises as the eye closes)")
    print(f"mediapipe {mp.__version__}, median detect time {np.median([r[6] for r in rows]):.0f} ms on this machine")


def video_mode(names: list[str], stretches: int, length: int) -> None:
    """The browser's mode: stretches of consecutive frames, and where DROZY's landmarks put the face when it is missed."""
    def describe(rows: list[tuple[float, ...]]) -> str:
        if not rows:
            return "n=0"
        width, cx, cy, down = np.median(np.array(rows), axis=0)
        return f"n={len(rows):4d} face width {width:3.0f} px  centre ({cx:3.0f},{cy:3.0f})  nose/chin {down:.2f}"

    for video in videos(names):
        annot = annotations(video.stem)
        cap = cv2.VideoCapture(str(video))
        total, fps = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)), cap.get(cv2.CAP_PROP_FPS)
        hit, miss, seen, found = [], [], 0, 0
        with landmarker(RunningMode.VIDEO) as model:
            timestamp = 0
            for start in np.linspace(0, total - length - 1, stretches).astype(int):
                cap.set(cv2.CAP_PROP_POS_FRAMES, int(start))
                for index in range(start, start + length):
                    ok, frame = cap.read()
                    if not ok:
                        break
                    timestamp += int(1000 / fps)
                    face = bool(model.detect_for_video(rgb(frame), timestamp).face_landmarks)
                    seen += 1
                    found += face
                    points = annot[index].reshape(68, 2)
                    if points.any():
                        eyes_y = points[36:48, 1].mean()
                        down = (points[30, 1] - eyes_y) / max(1e-6, points[8, 1] - eyes_y)  # crude head-down cue
                        width = points[:, 0].max() - points[:, 0].min()
                        (hit if face else miss).append((width, points[:, 0].mean(), points[:, 1].mean(), down))
        cap.release()
        print(f"{video.stem:>5}  VIDEO mode face found {found / seen:4.0%}\n"
              f"       found:  {describe(hit)}\n       missed: {describe(miss)}", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("mode", choices=["image", "video"])
    parser.add_argument("names", nargs="*", help="tests such as 1-3 (default: all)")
    parser.add_argument("--samples", type=int, default=120, help="image mode: frames per video")
    parser.add_argument("--stretches", type=int, default=8, help="video mode: stretches per video")
    parser.add_argument("--length", type=int, default=90, help="video mode: consecutive frames per stretch")
    args = parser.parse_args()
    if not DROZY.exists() or not MODEL.exists():
        raise SystemExit(f"needs {DROZY.relative_to(ROOT)} (docs: goals/G2-fatigue-model.md) and "
                         f"{MODEL.relative_to(ROOT)} (make prefetch)")
    if args.mode == "image":
        image_mode(args.names, args.samples)
    else:
        video_mode(args.names, args.stretches, args.length)


if __name__ == "__main__":
    main()
