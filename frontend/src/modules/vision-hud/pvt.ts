/**
 * PVT-B: the 3-minute Psychomotor Vigilance Test (goal G3, `goals/G3-pvt.md`).
 *
 * Logic only: no DOM, and no `Date`, `performance` or timers of its own. The clock and the random source are
 * injected, so the acceptance test (`src/acceptance/pvt.test.ts`) runs it with fake timers and the UI runs it with
 * `performance.now()` and `window.setTimeout`.
 *
 * It is not a medical device: 355 ms was calibrated on a handheld PVT-192, not on a laptop keyboard and screen.
 */

import { createStore, type StoreApi } from "zustand/vanilla";

/**
 * The paper's parameters: Basner, Mollicone & Dinges (2011), Sections 2.2 and 2.3, source `basner-2011-pvtb` in
 * `shared/sources.json`, as written down in `goals/G3-pvt.md`.
 */
export const PVT_B = {
  /** Length of the test. */
  durationMs: 180_000,
  /** Inter-stimulus interval, 1-4 s, counted from the response or time-out that ended the previous trial. */
  minIntervalMs: 1_000,
  maxIntervalMs: 4_000,
  /** The reaction time is shown during the first second of that interval. */
  feedbackMs: 1_000,
  /** A reaction under 100 ms is a false start. */
  minValidMs: 100,
  /** A valid response of 355 ms or more is a lapse (the PVT-B criterion; 500 ms in the 10-minute PVT). */
  lapseMs: 355,
  /** 30 s without a response end the trial: one lapse, recorded with a 30 s reaction time. */
  timeoutMs: 30_000,
} as const;

export type PvtOutcome = "valid" | "false-start" | "timeout";

export interface PvtTrial {
  outcome: PvtOutcome;
  /**
   * Milliseconds from stimulus onset to the response; 30 000 for a time-out; null for a response made with no
   * stimulus on screen, where there is no onset to measure from.
   */
  reactionMs: number | null;
  lapse: boolean;
}

export interface PvtState {
  /** Before `start()`, during the 180 s, after them. */
  phase: "idle" | "running" | "done";
  stimulusVisible: boolean;
  /** The trial that just ended, during the first second after it; otherwise null. */
  feedback: PvtTrial | null;
  /** Every recorded trial, in order. */
  trials: readonly PvtTrial[];
}

export interface PvtClock {
  /** Milliseconds, from any origin. */
  now(): number;
  setTimeout(callback: () => void, ms: number): unknown;
  clearTimeout(handle: unknown): void;
}

/** The PVT fields of the contract's `biometrics` block (`shared/telemetry.schema.json`). */
export interface PvtResult {
  lastPvtMeanMs: number | null;
  lastPvtLapses: number | null;
}

export type PvtStore = StoreApi<{ biometrics: PvtResult }>;

/** A store with no PVT run yet: both fields are null, as the contract allows. */
export function createPvtStore(): PvtStore {
  return createStore<{ biometrics: PvtResult }>(() => ({
    biometrics: { lastPvtMeanMs: null, lastPvtLapses: null },
  }));
}

/**
 * The two numbers the contract keeps from a finished test.
 *
 * Team choices, not the paper's (see the notes in `goals/G3-pvt.md`):
 * - a mean reaction time in milliseconds: the paper reports response speed (1/RT), lapses and a performance score,
 *   but the contract has `lastPvtMeanMs`;
 * - time-outs stay out of the mean, since one 30 s trial would swamp it; each still counts as a lapse.
 * False starts are neither lapses nor part of the mean (that one is the paper's).
 */
export function summarizePvt(trials: readonly PvtTrial[]): PvtResult {
  let sum = 0;
  let validCount = 0;
  let lapses = 0;
  for (const trial of trials) {
    if (trial.lapse) lapses += 1;
    if (trial.outcome === "valid" && trial.reactionMs !== null) {
      sum += trial.reactionMs;
      validCount += 1;
    }
  }
  return { lastPvtMeanMs: validCount > 0 ? sum / validCount : null, lastPvtLapses: lapses };
}

export interface PvtSession {
  /** The 180 s start here; the first stimulus comes after a 1-4 s interval. */
  start(): void;
  /** The key press, timed with `clock.now()`. */
  respond(): void;
  state(): PvtState;
}

export interface PvtOptions {
  clock: PvtClock;
  /** A number in [0, 1), like `Math.random`. */
  random: () => number;
  /** Receives the result once, when the 180 s end. */
  store: PvtStore;
}

export function createPvt({ clock, random, store }: PvtOptions): PvtSession {
  let phase: PvtState["phase"] = "idle";
  let startedAt = 0;
  let stimulusOnsetAt: number | null = null;
  let feedback: PvtTrial | null = null;
  const trials: PvtTrial[] = [];

  let stimulusTimer: unknown = null;
  let timeoutTimer: unknown = null;
  let feedbackTimer: unknown = null;
  let endTimer: unknown = null;

  const cancel = (handle: unknown) => {
    if (handle !== null) clock.clearTimeout(handle);
  };

  /** Closes a trial: records it, shows it for a second and draws the interval to the next stimulus. */
  function endTrial(trial: PvtTrial): void {
    cancel(timeoutTimer);
    timeoutTimer = null;
    stimulusOnsetAt = null;
    trials.push(trial);

    feedback = trial;
    cancel(feedbackTimer);
    feedbackTimer = clock.setTimeout(() => {
      feedbackTimer = null;
      feedback = null;
    }, PVT_B.feedbackMs);

    scheduleStimulus();
  }

  /** A new interval; a stimulus that was pending (a false start arrived before it) is dropped. */
  function scheduleStimulus(): void {
    cancel(stimulusTimer);
    const interval = PVT_B.minIntervalMs + random() * (PVT_B.maxIntervalMs - PVT_B.minIntervalMs);
    stimulusTimer = clock.setTimeout(showStimulus, interval);
  }

  function showStimulus(): void {
    stimulusTimer = null;
    // No stimulus once the 180 s are over, whatever order the timers fire in.
    if (phase !== "running" || clock.now() - startedAt >= PVT_B.durationMs) return;
    cancel(feedbackTimer);
    feedbackTimer = null;
    feedback = null;
    stimulusOnsetAt = clock.now();
    timeoutTimer = clock.setTimeout(() => {
      timeoutTimer = null;
      endTrial({ outcome: "timeout", reactionMs: PVT_B.timeoutMs, lapse: true });
    }, PVT_B.timeoutMs);
  }

  function finish(): void {
    endTimer = null;
    phase = "done";
    for (const handle of [stimulusTimer, timeoutTimer, feedbackTimer]) cancel(handle);
    stimulusTimer = timeoutTimer = feedbackTimer = null;
    // Team choice: a trial still open at 180 s is discarded (the part of the paper we read does not say).
    stimulusOnsetAt = null;
    feedback = null;
    const result = summarizePvt(trials);
    store.setState((current) => ({ biometrics: { ...current.biometrics, ...result } }));
  }

  return {
    start() {
      if (phase !== "idle") return;
      phase = "running";
      startedAt = clock.now();
      endTimer = clock.setTimeout(finish, PVT_B.durationMs);
      scheduleStimulus();
    },

    respond() {
      if (phase !== "running") return;
      if (clock.now() - startedAt >= PVT_B.durationMs) return; // the end timer has not fired yet
      if (stimulusOnsetAt === null) {
        endTrial({ outcome: "false-start", reactionMs: null, lapse: false });
        return;
      }
      const reactionMs = clock.now() - stimulusOnsetAt;
      if (reactionMs < PVT_B.minValidMs) {
        endTrial({ outcome: "false-start", reactionMs, lapse: false });
      } else {
        endTrial({ outcome: "valid", reactionMs, lapse: reactionMs >= PVT_B.lapseMs });
      }
    },

    state() {
      return { phase, stimulusVisible: stimulusOnsetAt !== null, feedback, trials: [...trials] };
    },
  };
}
