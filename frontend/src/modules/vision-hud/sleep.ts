/**
 * Eyes held closed, as a score from 0 to 1 that the worker folds into `fatigueScore`.
 *
 * PERCLOS is a share of the last minute, so someone who falls asleep after a while awake needs about 7 s of closed
 * eyes to reach the engine's 0.11, and that rule is only a warning. This reads the current closure instead: nothing for a blink, 0.7 (the engine's
 * `fatigue-score-high` threshold) after about 3 s, 1 after 4 s.
 *
 * All four constants are team assumptions with no registered source and no calibration: they say "the eyes have
 * been shut for seconds", not that the person is asleep.
 */

export const CLOSURE_FROM_S = 1; // a closure shorter than this is a blink or a slow blink: no score
export const CLOSURE_FULL_S = 4; // closed this long scores 1; the engine's 0.7 is crossed at 3.1 s
export const CLOSURE_HOLD_S = 5; // the score stays this long after the eyes open, so a 2 s poll cannot miss it
const MAX_GAP_S = 0.25; // as the yawn detector: a face lost for longer ends the closure

const EPS = 1e-9;

/** Feed one eye state per processed frame, in time order: true closed, false open, null when there is no face. */
export class SustainedClosure {
  private start: number | null = null; // when the current closure began
  private last = 0; // the last frame that confirmed it
  private held: { score: number; at: number }[] = []; // scores still being held, highest first

  push(timeS: number, closed: boolean | null): void {
    if (this.start !== null && timeS - this.last > MAX_GAP_S + EPS) this.start = null;
    if (closed === null) return;
    if (!closed) {
      this.start = null;
      return;
    }
    this.start ??= timeS;
    this.last = timeS;
    const now = ramp(timeS - this.start);
    if (now <= 0) return;
    // A lower score reached later outlives a higher one reached earlier: keep both, drop what it supersedes.
    this.held = [...this.held.filter((h) => h.score > now && timeS - h.at <= CLOSURE_HOLD_S + EPS), { score: now, at: timeS }];
  }

  /** The score at `timeS`: the highest closure score still held, 0 when none is. */
  score(timeS: number): number {
    return this.current(timeS);
  }

  reset(): void {
    this.start = null;
    this.held = [];
  }

  private current(timeS: number): number {
    return this.held.find((h) => timeS - h.at <= CLOSURE_HOLD_S + EPS)?.score ?? 0;
  }
}

const ramp = (closedForS: number) => Math.min(1, Math.max(0, (closedForS - CLOSURE_FROM_S) / (CLOSURE_FULL_S - CLOSURE_FROM_S)));
