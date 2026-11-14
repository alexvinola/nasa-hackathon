/**
 * The browser's port of the fatigue model against `data/fatigue_model.json` (weights and constants) and against the
 * values `data/pulsar_vision/fatigue_features.py` computes on the same synthetic series (`window_features`,
 * `predict_proba` and `fatigue_score`, run on 2026-11-14 with the shipped model).
 */

import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import {
  estimateFatigue,
  FATIGUE_MODEL,
  LONG_CLOSURE_S,
  MAX_GAP_S,
  MIN_FACE_FRACTION,
  MIN_WINDOW_FRAMES,
  NOD_OFF_DEG,
  NOD_ON_DEG,
  openEpisodes,
  predict,
  WINDOW_S,
  windowFeatures,
  type Sample,
} from "./fatigueModel";
import { BLINK } from "./thresholds";
import { YAWN_PARAMS } from "./yawn";

const FPS = 15;
const NAN = Number.NaN;

/** `frames` frames at 15 fps: open eyes, level head, closed mouth, a face in every one. */
const quiet = (frames = 900): Sample[] =>
  Array.from({ length: frames }, (_, i) => ({ t: i / FPS, face: true, closed: 0, pitch: 0, mouth: 0.05 }));

/** The series the Python reference was computed on: two blinks, one long closure, a nod, a yawn and a lost face. */
function eventful(): Sample[] {
  const samples = quiet().map((s, i) => ({ ...s, pitch: 2 * Math.sin(i / 40) }));
  const between = (from: number, to: number, change: (s: Sample) => void) => samples.slice(from, to + 1).forEach(change);
  for (const [from, to] of [[30, 31], [100, 102], [300, 311]]) between(from, to, (s) => (s.closed = 1));
  between(600, 630, (s) => (s.pitch += 14));
  between(700, 720, (s) => (s.mouth = 0.4));
  between(500, 520, (s) => Object.assign(s, { face: false, closed: NAN, pitch: NAN, mouth: NAN }));
  return samples;
}

describe("the model file", () => {
  const model = JSON.parse(readFileSync(resolve(__dirname, "../../../../data/fatigue_model.json"), "utf8"));

  it("has the weights the browser applies", () => {
    expect(model.features_version).toBe(FATIGUE_MODEL.featuresVersion);
    expect(model.features).toEqual(FATIGUE_MODEL.features);
    expect(model.mean).toEqual(FATIGUE_MODEL.mean);
    expect(model.std).toEqual(FATIGUE_MODEL.std);
    expect(model.coef).toEqual(FATIGUE_MODEL.coef);
    expect(model.intercept).toEqual(FATIGUE_MODEL.intercept);
    expect(model.classes).toEqual(FATIGUE_MODEL.classes);
    expect(FATIGUE_MODEL.classes.map((name) => model.score.weights[name])).toEqual(FATIGUE_MODEL.scoreWeights);
  });

  it("has the constants the browser uses", () => {
    expect(model.constants).toMatchObject({
      window_s: WINDOW_S,
      min_face_fraction: MIN_FACE_FRACTION,
      min_window_frames: MIN_WINDOW_FRAMES,
      max_gap_s: MAX_GAP_S,
      long_closure_s: LONG_CLOSURE_S,
      nod_on_deg: NOD_ON_DEG,
      nod_off_deg: NOD_OFF_DEG,
      pitch_down_sign: 1,
      blendshape_closed: BLINK,
    });
    expect(model.eye_closure.method).toBe("blendshape");
    expect(model.normalisation.variant).toBe("absolute");
    expect(model.yawn_detector).toMatchObject({
      threshold: YAWN_PARAMS.threshold,
      min_duration_s: YAWN_PARAMS.minDurationS,
      release_factor: YAWN_PARAMS.releaseFactor,
      max_gap_s: YAWN_PARAMS.maxGapS,
    });
  });
});

describe("openEpisodes", () => {
  it("closes on the first value below the off level and keeps an episode open at the end", () => {
    expect(openEpisodes([0, 1, 2, 3, 4], [0, 1, 1, 0, 1], 0.5, 0.5, 5)).toEqual([[1, 2], [4, 4]]);
  });

  it("bridges a short gap without a face and closes on a long one", () => {
    expect(openEpisodes([0, 0.1, 0.2, 0.3], [1, NAN, NAN, 1], 0.5, 0.5, MAX_GAP_S)).toEqual([[0, 0], [0.3, 0.3]]);
    expect(openEpisodes([0, 0.1, 0.2], [1, NAN, 1], 0.5, 0.5, MAX_GAP_S)).toEqual([[0, 0.2]]);
  });
});

describe("windowFeatures and predict, against the Python", () => {
  it("gives the Python's features and score on an eventful window", () => {
    const estimate = estimateFatigue(eventful())!;
    const expected = [0.019340159271899887, 2.04778156996587, 0.1666666666666663, 1.023890784982935, 1.0, 3.0190522055124576, 1.023890784982935];
    estimate.features.forEach((value, i) => expect(value).toBeCloseTo(expected[i], 9));
    [0.243363, 0.250928, 0.505709].forEach((p, k) => expect(estimate.probabilities[k]).toBeCloseTo(p, 5));
    expect(estimate.score).toBeCloseTo(0.631173, 5);
    expect(estimate.label).toBe("drowsy");
  });

  it("treats a window without blinks as the Python does: the blink duration is missing, not zero", () => {
    const features = windowFeatures(quiet())!;
    expect(features).toEqual([0, 0, NAN, 0, 0, 0, 0]);
    const estimate = predict(features);
    [0.354761, 0.339066, 0.306174].forEach((p, k) => expect(estimate.probabilities[k]).toBeCloseTo(p, 5));
    expect(estimate.score).toBeCloseTo(0.475706, 5);
    expect(estimate.label).toBe("alert");
  });
});

describe("windows that give no score", () => {
  it("refuses a window with too few frames", () => {
    expect(estimateFatigue(quiet(MIN_WINDOW_FRAMES - 1))).toBeNull();
    expect(estimateFatigue(quiet(MIN_WINDOW_FRAMES))).not.toBeNull();
  });

  it("refuses a window where the face is missing in more than a fifth of the frames", () => {
    const lost = (frames: number) =>
      quiet().map((s, i) => (i < frames ? { ...s, face: false, closed: NAN, pitch: NAN, mouth: NAN } : s));
    expect(estimateFatigue(lost(181))).toBeNull();
    expect(estimateFatigue(lost(180))).not.toBeNull();
  });
});
