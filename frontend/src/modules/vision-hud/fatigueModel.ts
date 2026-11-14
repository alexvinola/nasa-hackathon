/**
 * The fatigue model trained on UTA-RLDD (goal G2), ported from Python so the browser gives the numbers that were
 * validated: `data/pulsar_vision/fatigue_features.py` is the single place for the definitions (section WHAT SHIPS),
 * and `data/fatigue_model.json` carries the weights.
 *
 * A second reading, shown next to the worker's fixed-formula `fatigueScore`: it does not go into the contract and
 * the rules engine does not see it. Out of fold on RLDD the model's score was not shown to beat the fixed formula
 * (`data/out/fatigue_report.md`), and its scale differs: a fully alert window scores about 0.45.
 *
 * `fatigueModel.test.ts` checks these constants against `fatigue_model.json` and the arithmetic against values the
 * Python computed on the same series.
 */

import { countYawns } from "./yawn";

/** `fatigue_model.json`: features in the model's order, their training mean and std, and the logistic weights. */
export const FATIGUE_MODEL = {
  featuresVersion: 1,
  features: [
    "perclos",
    "blink_rate_per_min",
    "mean_blink_duration_s",
    "long_closure_rate_per_min",
    "yawns_per_min",
    "head_pitch_std_deg",
    "nods_per_min",
  ],
  mean: [0.061404, 13.784452, 0.163878, 0.787697, 0.023093, 2.429289, 0.327818],
  std: [0.092453, 11.825457, 0.060204, 2.019035, 0.157189, 1.735511, 0.847971],
  coef: [
    [-0.113774, -0.052413, -0.153245, -0.146144, -0.018155, -0.042616, -0.011983],
    [-0.014482, 0.045739, -0.027574, -0.011087, -0.051924, 0.038681, 0.018819],
    [0.128255, 0.006675, 0.180819, 0.157231, 0.070079, 0.003935, -0.006836],
  ],
  intercept: [-0.196448, 0.112094, 0.084354],
  classes: ["alert", "low_vigilance", "drowsy"],
  scoreWeights: [0, 0.5, 1], // fatigueScore = 0.5 × P(low_vigilance) + 1.0 × P(drowsy)
} as const;

// `constants` in fatigue_model.json. The last five are team assumptions (see fatigue_features.py).
export const WINDOW_S = 60;
export const MODEL_BLINK = 0.5; // `blendshape_closed`: the eye closure the model was trained with, not the HUD's BLINK
export const MAX_GAP_S = 0.25;
export const MIN_WINDOW_FRAMES = 450; // at least 7.5 processed frames a second on average
export const MIN_FACE_FRACTION = 0.8; // a window with a face in fewer of its frames gives no score
export const LONG_CLOSURE_S = 0.5; // closures at least this long are counted apart from blinks
export const NOD_ON_DEG = 10; // the head drops this far below the window's median pitch
export const NOD_OFF_DEG = 5; // and the nod ends when it comes back within this

const EPS = 1e-9;

/** One processed frame. A frame with no face has `face` false and NaN in the three signals: missing is never 0. */
export type Sample = {
  t: number; // seconds
  face: boolean;
  closed: number; // 1 when (eyeBlinkLeft + eyeBlinkRight) / 2 > MODEL_BLINK, else 0
  pitch: number; // head pitch in degrees, atan2(m[6], m[10]) of the facial transformation matrix
  mouth: number; // mouth opening ratio (./yawn)
};

export type FatigueEstimate = {
  features: number[]; // in FATIGUE_MODEL.features order; NaN where a feature is missing
  probabilities: number[]; // alert, low_vigilance, drowsy
  score: number;
  label: (typeof FATIGUE_MODEL.classes)[number];
};

/** `detector.open_episodes`: stretches at or above `on`, kept open while at or above `off`, as [start, end] times. */
export function openEpisodes(times: readonly number[], values: readonly number[], on: number, off: number, maxGapS: number): [number, number][] {
  const episodes: [number, number][] = [];
  let open = false;
  let start = 0;
  let last = 0;
  times.forEach((t, i) => {
    if (open && t - last > maxGapS + EPS) {
      episodes.push([start, last]);
      open = false;
    }
    const value = values[i];
    if (Number.isNaN(value)) return;
    if (!open) {
      if (value >= on) {
        open = true;
        start = last = t;
      }
    } else if (value >= off) {
      last = t;
    } else {
      episodes.push([start, last]);
      open = false;
    }
  });
  if (open) episodes.push([start, last]);
  return episodes;
}

function median(values: number[]): number {
  if (!values.length) return Number.NaN;
  const sorted = [...values].sort((a, b) => a - b);
  const middle = Math.floor(sorted.length / 2);
  return sorted.length % 2 ? sorted[middle] : (sorted[middle - 1] + sorted[middle]) / 2;
}

const mean = (values: number[]) => values.reduce((a, b) => a + b, 0) / values.length;

/** The seven features of one 60 s window (its frames, in time order), or null when the window is not usable. */
export function windowFeatures(samples: readonly Sample[]): number[] | null {
  const frames = samples.length;
  const faceFrames = samples.filter((s) => s.face).length;
  if (frames < MIN_WINDOW_FRAMES || faceFrames < MIN_FACE_FRACTION * frames - EPS) return null;
  const seen = samples.filter((s) => !Number.isNaN(s.closed));
  if (!seen.length) return null;
  const observedMin = (faceFrames / frames) * (WINDOW_S / 60);
  const times = samples.map((s) => s.t);

  const period = median(times.slice(1).map((t, i) => t - times[i])); // each closed frame stands for one frame period
  const closed = samples.map((s) => s.closed);
  const durations = openEpisodes(times, closed, 0.5, 0.5, MAX_GAP_S).map(([start, end]) => end - start + period);
  const blinks = durations.filter((d) => d < LONG_CLOSURE_S - EPS);

  const pitch = samples.map((s) => s.pitch).filter((p) => !Number.isNaN(p));
  const pitchMean = pitch.length ? mean(pitch) : Number.NaN;
  const pitchMedian = median(pitch);
  const drop = samples.map((s) => s.pitch - pitchMedian); // positive pitch is chin towards the chest
  const nods = pitch.length ? openEpisodes(times, drop, NOD_ON_DEG, NOD_OFF_DEG, MAX_GAP_S).length : 0;

  return [
    seen.filter((s) => s.closed > 0.5).length / seen.length,
    blinks.length / observedMin,
    blinks.length ? mean(blinks) : Number.NaN,
    (durations.length - blinks.length) / observedMin,
    countYawns(times, samples.map((s) => s.mouth)) / (WINDOW_S / 60),
    pitch.length ? Math.sqrt(mean(pitch.map((p) => (p - pitchMean) ** 2))) : Number.NaN,
    nods / observedMin,
  ];
}

/** Class probabilities and the score for one window's features. A missing feature counts as the training mean. */
export function predict(features: readonly number[]): FatigueEstimate {
  const { mean: mu, std, coef, intercept, classes, scoreWeights } = FATIGUE_MODEL;
  const z = features.map((x, i) => (Number.isNaN(x) ? 0 : (x - mu[i]) / std[i]));
  const logits = coef.map((row, k) => intercept[k] + row.reduce((sum, c, i) => sum + c * z[i], 0));
  const top = Math.max(...logits);
  const exp = logits.map((l) => Math.exp(l - top));
  const total = exp.reduce((a, b) => a + b, 0);
  const probabilities = exp.map((e) => e / total);
  return {
    features: [...features],
    probabilities,
    score: probabilities.reduce((sum, p, k) => sum + p * scoreWeights[k], 0),
    label: classes[probabilities.indexOf(Math.max(...probabilities))],
  };
}

/** The estimate for one window, or null when the window is not usable: never a score computed from zeros. */
export function estimateFatigue(samples: readonly Sample[]): FatigueEstimate | null {
  const features = windowFeatures(samples);
  return features ? predict(features) : null;
}
