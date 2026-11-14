/**
 * The browser's yawn counter against the Python detector it ports (`data/tests/test_detector.py`, same synthetic
 * series and expectations) and against the calibrated parameters in `data/out/yawn_params.json`.
 */

import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import { countYawns, MOUTH_LANDMARKS, mouthOpenRatio, YAWN_PARAMS, YawnDetector, type YawnParams } from "./yawn";

const FPS = 15;
const NAN = Number.NaN;

/** A 15 fps series from (value, number of frames) segments, as `series` in the Python tests. */
function series(...segments: [number, number][]): [number[], number[]] {
  const values = segments.flatMap(([value, frames]) => Array<number>(frames).fill(value));
  return [values.map((_, i) => i / FPS), values];
}

/** The Python tests' default parameters: threshold 0.3, 1 s, no hysteresis, 0.25 s gap. */
const params = (overrides: Partial<YawnParams> = {}): YawnParams => ({
  threshold: 0.3,
  minDurationS: 1.0,
  releaseFactor: 1.0,
  maxGapS: 0.25,
  ...overrides,
});

const count = (s: [number[], number[]], p: YawnParams = params()) => countYawns(s[0], s[1], p);

describe("yawn detector (port of data/pulsar_vision/detector.py)", () => {
  it("finds no yawn with the mouth closed", () => {
    expect(count(series([0.02, 150]))).toBe(0);
  });

  it("counts one long opening once", () => {
    expect(count(series([0.02, 30], [0.5, 45], [0.02, 30]))).toBe(1);
  });

  it("ignores talking bursts shorter than the minimum duration", () => {
    const bursts = Array.from({ length: 4 }, () => [[0.02, 10], [0.45, 7]] as [number, number][]).flat();
    expect(count(series(...bursts, [0.02, 10]))).toBe(0);
  });

  it("measures the minimum duration between the first and the last open frame", () => {
    expect(count(series([0, 5], [0.5, 16], [0, 5]))).toBe(1); // 16 frames span exactly 1.0 s
    expect(count(series([0, 5], [0.5, 15], [0, 5]))).toBe(0); // 15 frames span 0.933 s
  });

  it("treats the threshold as inclusive", () => {
    const s = series([0, 5], [0.3, 20], [0, 5]);
    expect(count(s, params({ threshold: 0.3 }))).toBe(1);
    expect(count(s, params({ threshold: 0.31 }))).toBe(0);
  });

  it("counts two separate yawns twice", () => {
    expect(count(series([0.02, 15], [0.6, 30], [0.02, 45], [0.6, 30], [0.02, 15]))).toBe(2);
  });

  it("counts a yawn still open when the series ends", () => {
    expect(count(series([0.02, 15], [0.6, 30]))).toBe(1);
  });

  it("keeps one yawn through a dip thanks to hysteresis", () => {
    const s = series([0.02, 10], [0.5, 12], [0.27, 2], [0.5, 12], [0.02, 10]);
    expect(count(s, params({ releaseFactor: 0.8 }))).toBe(1);
    expect(count(s, params({ releaseFactor: 1.0 }))).toBe(0); // the dip splits it into two short stretches
  });

  it("never opens below the threshold, hysteresis or not", () => {
    expect(count(series([0.02, 10], [0.27, 40], [0.02, 10]), params({ releaseFactor: 0.8 }))).toBe(0);
  });

  it("bridges a short gap of frames without a face", () => {
    expect(count(series([0.02, 10], [0.5, 12], [NAN, 2], [0.5, 12], [0.02, 10]))).toBe(1);
  });

  it("closes the stretch when the face is lost for longer than the gap", () => {
    expect(count(series([0.02, 10], [0.5, 12], [NAN, 4], [0.5, 12], [0.02, 10]))).toBe(0);
  });

  it("treats a missing frame differently from a closed mouth", () => {
    expect(count(series([0.02, 10], [0.5, 12], [NAN, 2], [0.5, 12], [0.02, 10]))).toBe(1);
    expect(count(series([0.02, 10], [0.5, 12], [0, 2], [0.5, 12], [0.02, 10]))).toBe(0);
  });

  it("never opens on frames without a face", () => {
    expect(count(series([NAN, 100]))).toBe(0);
  });

  it("does not extend a yawn over frames without a face", () => {
    expect(count(series([0.5, 14], [NAN, 60]))).toBe(0); // 14 open frames span 0.87 s, then the face is lost
    expect(count(series([0.5, 20], [NAN, 60]))).toBe(1);
  });

  it("handles an empty series", () => {
    expect(countYawns([], [])).toBe(0);
  });

  it("reports the yawn on the frame where it reaches the minimum duration", () => {
    const detector = new YawnDetector(params());
    const [times, ratios] = series([0.02, 5], [0.5, 30]);
    const fired = times.map((t, i) => detector.push(t, ratios[i]));
    expect(fired.filter(Boolean)).toHaveLength(1);
    expect(fired.indexOf(true)).toBe(5 + 15); // the 16th open frame is 1.0 s after the first
  });

  it("rejects a release factor outside (0, 1]", () => {
    expect(() => new YawnDetector(params({ releaseFactor: 1.2 }))).toThrow();
    expect(() => countYawns([0], [0.5, 0.5])).toThrow();
  });
});

describe("mouth opening ratio (port of data/pulsar_vision/mouth.py)", () => {
  /** A 478-point mesh at the origin with the four landmarks the formula reads. */
  function mesh(points: Record<number, [number, number]>) {
    const out = Array.from({ length: 478 }, () => ({ x: 0, y: 0, z: 0 }));
    for (const [i, [x, y]] of Object.entries(points)) out[Number(i)] = { x, y, z: 0 };
    return out;
  }
  const { upperInnerLip, lowerInnerLip, rightEyeOuter, leftEyeOuter } = MOUTH_LANDMARKS;

  it("divides the lip gap by the eye-corner distance, in pixels", () => {
    const face = mesh({
      [rightEyeOuter]: [0.4, 0.4],
      [leftEyeOuter]: [0.6, 0.4], // 0.2 × 640 = 128 px apart
      [upperInnerLip]: [0.5, 0.6],
      [lowerInnerLip]: [0.5, 0.6 + 32 / 480], // 32 px apart
    });
    expect(mouthOpenRatio(face, 640, 480)).toBeCloseTo(32 / 128, 9);
  });

  it("scales x and y by their own image dimension", () => {
    // Same normalised points on a 640x480 frame: a horizontal gap would be stretched by 4/3 if not scaled per axis.
    const face = mesh({
      [rightEyeOuter]: [0.4, 0.4],
      [leftEyeOuter]: [0.6, 0.4],
      [upperInnerLip]: [0.5, 0.6],
      [lowerInnerLip]: [0.5 + 0.05, 0.6],
    });
    expect(mouthOpenRatio(face, 640, 480)).toBeCloseTo(0.05 / 0.2, 9);
    expect(mouthOpenRatio(face, 480, 640)).toBeCloseTo(0.05 / 0.2, 9);
  });

  it("is missing, never zero, without a face or with coincident eye corners", () => {
    expect(mouthOpenRatio(undefined, 640, 480)).toBeNaN();
    expect(mouthOpenRatio(mesh({}), 640, 480)).toBeNaN();
  });
});

describe("calibrated parameters", () => {
  it("match data/out/yawn_params.json", () => {
    const file = resolve(__dirname, "../../../../data/out/yawn_params.json");
    const calibrated = JSON.parse(readFileSync(file, "utf-8"));
    expect(calibrated.variant).toBe("absolute");
    expect(YAWN_PARAMS).toEqual({
      threshold: calibrated.threshold,
      releaseFactor: calibrated.release_factor,
      minDurationS: calibrated.min_duration_s,
      maxGapS: calibrated.max_gap_s,
    });
    expect(calibrated.feature.landmarks).toEqual({
      upper_inner_lip: MOUTH_LANDMARKS.upperInnerLip,
      lower_inner_lip: MOUTH_LANDMARKS.lowerInnerLip,
      right_eye_outer: MOUTH_LANDMARKS.rightEyeOuter,
      left_eye_outer: MOUTH_LANDMARKS.leftEyeOuter,
    });
  });
});
