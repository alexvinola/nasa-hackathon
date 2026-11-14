"""How reliable is Gemma's eye-state check (POST /vision/verify)? Labelled MRL Eye crops, open vs closed.

uv run --project backend --with pillow python research/llm/eye_state_probe.py [per_class]

MRL images are small infrared crops of one eye, harder than a webcam face: treat the result as a lower bound.
Needs data/raw/mrl-eye/mrlEyes_2018_01.zip (downloaded by hand, see research/nasa-data/README.md).
"""

import base64
import io
import random
import sys
import time
import zipfile
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from PIL import Image  # noqa: E402

from pulsar.vision.verify import look  # noqa: E402

ZIP = ROOT / "data" / "raw" / "mrl-eye" / "mrlEyes_2018_01.zip"


def sample(per_class: int):
    with zipfile.ZipFile(ZIP) as archive:
        names = [n for n in archive.namelist() if n.endswith(".png")]
        by_state = {"closed": [], "open": []}
        for name in names:  # subject_image_gender_glasses_eyestate_reflections_lighting_sensor.png
            fields = Path(name).stem.split("_")
            by_state["open" if fields[4] == "1" else "closed"].append(name)
        rng = random.Random(7)
        for state, pool in by_state.items():
            for name in rng.sample(pool, per_class):
                image = Image.open(io.BytesIO(archive.read(name))).convert("RGB").resize((224, 224))
                buffer = io.BytesIO()
                image.save(buffer, "JPEG", quality=90)
                yield name, state, base64.b64encode(buffer.getvalue()).decode()


def main() -> None:
    per_class = int(sys.argv[1]) if len(sys.argv) > 1 else 25
    results, started = Counter(), time.perf_counter()
    for name, truth, image in sample(per_class):
        answer = look(image).eyes
        results[(truth, answer)] += 1
    total = sum(results.values())
    decided = {k: v for k, v in results.items() if k[1] != "unclear"}
    right = sum(v for (truth, answer), v in decided.items() if truth == answer)
    print(f"{total} crops, {time.perf_counter() - started:.0f} s")
    for truth in ("open", "closed"):
        row = {answer: results[(truth, answer)] for answer in ("open", "closed", "unclear")}
        print(f"  truth {truth:<6} -> {row}")
    print(f"answered {sum(decided.values())}/{total}; accuracy when it answers {right}/{sum(decided.values())}"
          f" = {right / max(1, sum(decided.values())):.0%}")


if __name__ == "__main__":
    main()
