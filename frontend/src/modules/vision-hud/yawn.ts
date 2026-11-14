/**
 * Yawn counting, ported from the Python calibration so the browser and the measured numbers agree.
 *
 * - Feature: `data/pulsar_vision/mouth.py`. Gap between the inner lip centres divided by the distance between the
 *   outer eye corners, both in pixels, so it does not depend on how far the face is from the camera.
 * - Detector: `data/pulsar_vision/detector.py` (`open_episodes` + `yawns_from_episodes`) as a streaming state machine.
 * - Parameters: `data/out/yawn_params.json`, calibrated on YawDD with leave-subject-out validation
 *   (`make yawns`; source `yawdd`). Out of fold: 88/102 yawning videos detected, 3/100 talking and 0/105 normal
 *   videos with a false yawn. Calibrated on drivers in cars, not on a laptop webcam: a measured starting point.
 *
 * `yawn.test.ts` replays the Python detector tests and checks these constants against `yawn_params.json`.
 */

/** Indices in MediaPipe's 478-point face mesh. */
export const MOUTH_LANDMARKS = {
  upperInnerLip: 13,
  lowerInnerLip: 14,
  rightEyeOuter: 33,
  leftEyeOuter: 263,
} as const;

export type YawnParams = {
  threshold: number; // ratio at which the mouth counts as open
  releaseFactor: number; // it stays open while the ratio is at least releaseFactor × threshold
  minDurationS: number; // an open stretch this long is a yawn
  maxGapS: number; // frames without a face may bridge at most this much time
};

export const YAWN_PARAMS: YawnParams = {
  threshold: 0.26,
  releaseFactor: 0.8,
  minDurationS: 1.0,
  maxGapS: 0.25,
};

type Point = { x: number; y: number };

/**
 * Mouth opening ratio of one face; NaN when the face is missing or degenerate (missing is never 0).
 * MediaPipe normalises x by the image width and y by its height, so both are scaled back before measuring.
 */
export function mouthOpenRatio(landmarks: readonly Point[] | undefined, width: number, height: number): number {
  if (!landmarks) return Number.NaN;
  const { upperInnerLip, lowerInnerLip, rightEyeOuter, leftEyeOuter } = MOUTH_LANDMARKS;
  const [upper, lower, right, left] = [upperInnerLip, lowerInnerLip, rightEyeOuter, leftEyeOuter].map((i) => landmarks[i]);
  if (!upper || !lower || !right || !left) return Number.NaN;
  const dist = (a: Point, b: Point) => Math.hypot((a.x - b.x) * width, (a.y - b.y) * height);
  const eyes = dist(right, left);
  return eyes > 0 ? dist(upper, lower) / eyes : Number.NaN;
}

const EPS = 1e-9; // durations are differences of frame times: tolerate float rounding, as the Python does

/**
 * Feed one `(time, ratio)` pair per processed frame, in time order; `push` returns true on the frame where an open
 * stretch first reaches the minimum duration, so each yawn is counted once however long it lasts.
 *
 * Open on ratio ≥ threshold; stay open while ratio ≥ releaseFactor × threshold; close on the first frame below it.
 * A NaN ratio (no face) neither opens nor closes, but more than maxGapS since the last frame that kept the mouth open
 * closes the stretch. Needs frames closer than maxGapS: below about 4 fps nothing can be counted.
 */
export class YawnDetector {
  private open = false;
  private start = 0;
  private last = 0;
  private counted = false;

  constructor(private readonly params: YawnParams = YAWN_PARAMS) {
    if (!(params.releaseFactor > 0 && params.releaseFactor <= 1)) throw new Error("releaseFactor must be in (0, 1]");
  }

  push(timeS: number, ratio: number): boolean {
    const { threshold, releaseFactor, minDurationS, maxGapS } = this.params;
    if (this.open && timeS - this.last > maxGapS + EPS) this.open = false;
    if (Number.isNaN(ratio)) return false;
    if (!this.open) {
      if (ratio < threshold) return false;
      this.open = true;
      this.start = this.last = timeS;
      this.counted = false;
    } else if (ratio >= releaseFactor * threshold) {
      this.last = timeS;
    } else {
      this.open = false;
      return false;
    }
    if (!this.counted && this.last - this.start >= minDurationS - EPS) {
      this.counted = true;
      return true;
    }
    return false;
  }

  reset(): void {
    this.open = false;
    this.counted = false;
  }
}

/** Counts the yawns in a recorded series (times in seconds): the batch form of `YawnDetector`, used by the tests. */
export function countYawns(timesS: readonly number[], ratios: readonly number[], params: YawnParams = YAWN_PARAMS): number {
  if (timesS.length !== ratios.length) throw new Error("timesS and ratios must have the same length");
  const detector = new YawnDetector(params);
  return timesS.reduce((n, t, i) => n + Number(detector.push(t, ratios[i])), 0);
}
