/**
 * G3 · PVT-B acceptance test (`goals/G3-pvt.md`, source `basner-2011-pvtb` in `shared/sources.json`).
 *
 * Every "Done when" point of the goal is one `describe` block below. The test drives the logic with Vitest fake
 * timers and a fixed random source: no browser, no UI. The numbers in the assertions are the goal's literals on
 * purpose, they are not imported from the implementation.
 *
 * ## What the implementation must provide: `frontend/src/modules/vision-hud/pvt.ts`
 *
 * ```ts
 * export type PvtOutcome = "valid" | "false-start" | "timeout";
 *
 * export interface PvtTrial {
 *   outcome: PvtOutcome;
 *   // ms from stimulus onset to the response; 30000 for a time-out;
 *   // null for a response made with no stimulus on screen (there is no onset to measure from)
 *   reactionMs: number | null;
 *   lapse: boolean;
 * }
 *
 * export interface PvtState {
 *   phase: "idle" | "running" | "done";   // before start() / during the 180 s / after them
 *   stimulusVisible: boolean;
 *   feedback: PvtTrial | null;            // the trial just finished, during the first 1 s after it; otherwise null
 *   trials: readonly PvtTrial[];          // every recorded trial, in order
 * }
 *
 * export interface PvtClock {             // injectable: the module never touches Date, performance or timers itself
 *   now(): number;                        // ms
 *   setTimeout(callback: () => void, ms: number): unknown;
 *   clearTimeout(handle: unknown): void;
 * }
 *
 * export interface PvtStore {             // the smallest store the goal needs; a Zustand vanilla store satisfies it
 *   getState(): { biometrics: { lastPvtMeanMs: number | null; lastPvtLapses: number | null } };
 * }
 * export function createPvtStore(): PvtStore;   // both fields start as null: no PVT has been run
 *
 * export interface PvtSession {
 *   start(): void;                        // the 180 s start here; the first stimulus comes after a 1-4 s interval
 *   respond(): void;                      // the key press, timed with clock.now()
 *   state(): PvtState;
 * }
 * export function createPvt(options: { clock: PvtClock; random: () => number; store: PvtStore }): PvtSession;
 * ```
 *
 * - `random()` returns a number in [0, 1) like `Math.random`; an interval lasts `1000 + random() * 3000` ms.
 * - The store is written once, when the 180 s end, and not before.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createPvt, createPvtStore, type PvtClock, type PvtTrial } from "../modules/vision-hud/pvt";

/** An arbitrary wall-clock time for start(): the test must not depend on the clock starting at zero. */
const T0 = 1_700_000_000_000;

const clock: PvtClock = {
  now: () => Date.now(),
  setTimeout: (callback, ms) => setTimeout(callback, ms),
  clearTimeout: (handle) => clearTimeout(handle as ReturnType<typeof setTimeout>),
};

/** A session started at T0 whose every interval is `1000 + random * 3000` ms long. */
function startPvt(random: number) {
  const store = createPvtStore();
  const session = createPvt({ clock, random: () => random, store });
  session.start();
  return { session, store };
}

/** Moves the fake clock to `ms` after start(), firing the timers due on the way. */
function at(ms: number): void {
  const delta = T0 + ms - Date.now();
  if (delta < 0) throw new Error(`the test clock is already past ${ms} ms`);
  vi.advanceTimersByTime(delta);
}

/** The three fields the goal asks for, whatever else the implementation keeps on a trial. */
const recorded = (trials: readonly PvtTrial[]) =>
  trials.map(({ outcome, reactionMs, lapse }) => ({ outcome, reactionMs, lapse }));

const valid = (reactionMs: number, lapse = false) => ({ outcome: "valid", reactionMs, lapse });
const falseStart = (reactionMs: number | null) => ({ outcome: "false-start", reactionMs, lapse: false });
const TIMEOUT = { outcome: "timeout", reactionMs: 30_000, lapse: true };

beforeEach(() => {
  vi.useFakeTimers();
  vi.setSystemTime(T0);
});

afterEach(() => {
  vi.useRealTimers();
});

describe("Intervals", () => {
  it("presents nothing before start()", () => {
    const session = createPvt({ clock, random: () => 0, store: createPvtStore() });
    vi.advanceTimersByTime(10_000);
    expect(session.state().phase).toBe("idle");
    expect(session.state().stimulusVisible).toBe(false);
    expect(session.state().trials).toHaveLength(0);
  });

  it("waits 1 s for the lowest random value", () => {
    const { session } = startPvt(0);
    expect(session.state().phase).toBe("running");
    at(999);
    expect(session.state().stimulusVisible).toBe(false);
    at(1000);
    expect(session.state().stimulusVisible).toBe(true);
  });

  it("waits 2.5 s for a random value of 0.5", () => {
    const { session } = startPvt(0.5);
    at(2499);
    expect(session.state().stimulusVisible).toBe(false);
    at(2500);
    expect(session.state().stimulusVisible).toBe(true);
  });

  it("never waits more than 4 s", () => {
    const { session } = startPvt(0.999);
    at(3990);
    expect(session.state().stimulusVisible).toBe(false);
    at(4000);
    expect(session.state().stimulusVisible).toBe(true);
  });

  it("draws a new interval after a response and shows the reaction time during its first second", () => {
    const { session } = startPvt(0.5);
    at(2500);
    at(2750);
    session.respond();

    expect(session.state().stimulusVisible).toBe(false);
    expect(session.state().feedback).toMatchObject(valid(250));
    at(2750 + 999);
    expect(session.state().feedback).toMatchObject(valid(250));
    at(2750 + 1000);
    expect(session.state().feedback).toBeNull();
    expect(session.state().stimulusVisible).toBe(false);

    at(2750 + 2499);
    expect(session.state().stimulusVisible).toBe(false);
    at(2750 + 2500);
    expect(session.state().stimulusVisible).toBe(true);
  });

  it("draws a new interval after a time-out and shows its 30 s during the first second", () => {
    const { session } = startPvt(0.5);
    at(2500);
    at(32_500);

    expect(session.state().stimulusVisible).toBe(false);
    expect(session.state().feedback).toMatchObject(TIMEOUT);
    at(32_500 + 999);
    expect(session.state().feedback).toMatchObject(TIMEOUT);
    at(32_500 + 1000);
    expect(session.state().feedback).toBeNull();

    at(32_500 + 2499);
    expect(session.state().stimulusVisible).toBe(false);
    at(32_500 + 2500);
    expect(session.state().stimulusVisible).toBe(true);
  });

  it("draws a new interval after a false start, dropping the stimulus that was pending", () => {
    const { session } = startPvt(0.5);
    at(1000);
    session.respond(); // nothing on screen yet

    at(2500); // when the stimulus would have appeared
    expect(session.state().stimulusVisible).toBe(false);
    at(1000 + 2499);
    expect(session.state().stimulusVisible).toBe(false);
    at(1000 + 2500);
    expect(session.state().stimulusVisible).toBe(true);
  });

  it("shows no feedback while a stimulus is on screen", () => {
    const { session } = startPvt(0); // a 1 s interval: the feedback fills it
    at(1000);
    at(1200);
    session.respond();
    expect(session.state().feedback).toMatchObject(valid(200));
    at(2200);
    expect(session.state().stimulusVisible).toBe(true);
    expect(session.state().feedback).toBeNull();
  });
});

describe("Every trial is recorded", () => {
  it("keeps each trial, in order, as valid, false start or time-out with its reaction time", () => {
    const { session } = startPvt(0);
    at(1000); // stimulus
    at(1200);
    session.respond(); // valid, 200 ms
    at(2200); // stimulus
    at(2250);
    session.respond(); // false start, 50 ms
    at(3000);
    session.respond(); // false start, nothing on screen
    at(4000); // stimulus
    at(34_000); // time-out

    expect(recorded(session.state().trials)).toEqual([valid(200), falseStart(50), falseStart(null), TIMEOUT]);
  });
});

describe("Valid response", () => {
  it("is a reaction of exactly 100 ms to a stimulus on screen", () => {
    const { session } = startPvt(0);
    at(1000);
    expect(session.state().stimulusVisible).toBe(true);
    at(1100);
    session.respond();
    expect(recorded(session.state().trials)).toEqual([valid(100)]);
    expect(session.state().stimulusVisible).toBe(false);
  });
});

describe("Lapse", () => {
  it("is not a valid response of 354 ms", () => {
    const { session } = startPvt(0);
    at(1000);
    at(1354);
    session.respond();
    expect(recorded(session.state().trials)).toEqual([valid(354, false)]);
  });

  it("is a valid response of 355 ms", () => {
    const { session } = startPvt(0);
    at(1000);
    at(1355);
    session.respond();
    expect(recorded(session.state().trials)).toEqual([valid(355, true)]);
  });

  it("is a time-out", () => {
    const { session } = startPvt(0);
    at(1000);
    at(31_000);
    expect(recorded(session.state().trials)).toEqual([TIMEOUT]);
  });
});

describe("False start", () => {
  it("is a response with no stimulus on screen: no reaction time, not a lapse", () => {
    const { session } = startPvt(0);
    at(500);
    session.respond();
    expect(recorded(session.state().trials)).toEqual([falseStart(null)]);
  });

  it("is a reaction of 99 ms: the trial ends, it is not a lapse", () => {
    const { session } = startPvt(0);
    at(1000);
    at(1099);
    session.respond();
    expect(recorded(session.state().trials)).toEqual([falseStart(99)]);
    expect(session.state().stimulusVisible).toBe(false);
  });

  it("does not enter the mean and does not count as a lapse", () => {
    const { session, store } = startPvt(0);
    // A press every 500 ms: each one lands in a fresh 1 s interval, so no stimulus ever appears.
    for (let ms = 500; ms < 180_000; ms += 500) {
      at(ms);
      session.respond();
    }
    at(180_000);

    const trials = recorded(session.state().trials);
    expect(trials).toHaveLength(359);
    expect(trials.every((trial) => trial.outcome === "false-start" && trial.reactionMs === null)).toBe(true);
    expect(store.getState().biometrics).toEqual({ lastPvtMeanMs: null, lastPvtLapses: 0 });
  });
});

describe("Time-out", () => {
  it("leaves the stimulus on screen until 30 s have passed", () => {
    const { session } = startPvt(0);
    at(1000);
    at(30_999);
    expect(session.state().stimulusVisible).toBe(true);
    expect(session.state().trials).toHaveLength(0);
  });

  it("ends the trial at 30 s, as one lapse with a 30 s reaction time", () => {
    const { session } = startPvt(0);
    at(1000);
    at(31_000);
    expect(session.state().stimulusVisible).toBe(false);
    expect(recorded(session.state().trials)).toEqual([TIMEOUT]);
  });

  it("is not reached by a response at 29 999 ms, which is a valid lapse", () => {
    const { session } = startPvt(0);
    at(1000);
    at(30_999);
    session.respond();
    at(31_500);
    expect(recorded(session.state().trials)).toEqual([valid(29_999, true)]);
  });
});

describe("Duration", () => {
  // With 2.5 s intervals and nobody responding: stimuli at 2.5, 35, 67.5, 100, 132.5 and 165 s,
  // time-outs at 32.5, 65, 97.5, 130 and 162.5 s. The sixth trial is still open at 180 s.

  it("runs until 180 s and then is done", () => {
    const { session } = startPvt(0.5);
    at(179_999);
    expect(session.state().phase).toBe("running");
    expect(session.state().stimulusVisible).toBe(true);
    at(180_000);
    expect(session.state().phase).toBe("done");
    expect(session.state().stimulusVisible).toBe(false);
  });

  it("discards the trial still open at 180 s", () => {
    const { session, store } = startPvt(0.5);
    at(180_000);
    expect(recorded(session.state().trials)).toEqual([TIMEOUT, TIMEOUT, TIMEOUT, TIMEOUT, TIMEOUT]);
    expect(store.getState().biometrics.lastPvtLapses).toBe(5);

    at(240_000); // its 30 s would have run out at 195 s
    expect(recorded(session.state().trials)).toHaveLength(5);
    expect(store.getState().biometrics.lastPvtLapses).toBe(5);
  });

  it("presents no stimulus after 180 s", () => {
    const { session } = startPvt(0.5);
    at(165_000);
    expect(session.state().stimulusVisible).toBe(true);
    at(178_000);
    session.respond(); // the next stimulus is due at 180.5 s
    at(180_000);
    expect(session.state().phase).toBe("done");
    for (let ms = 180_100; ms <= 190_000; ms += 100) {
      at(ms);
      expect(session.state().stimulusVisible).toBe(false);
    }
    expect(recorded(session.state().trials)).toHaveLength(6);
  });

  it("ignores responses after 180 s", () => {
    const { session, store } = startPvt(0.5);
    at(180_000);
    at(180_200);
    session.respond();
    at(190_000);
    session.respond();
    expect(recorded(session.state().trials)).toHaveLength(5);
    expect(store.getState().biometrics).toEqual({ lastPvtMeanMs: null, lastPvtLapses: 5 });
  });
});

describe("Result", () => {
  it("starts with no PVT in the store", () => {
    expect(createPvtStore().getState().biometrics).toEqual({ lastPvtMeanMs: null, lastPvtLapses: null });
  });

  it("writes the mean of the valid responses and the number of lapses when the test ends, not before", () => {
    const { session, store } = startPvt(0);
    at(1000); // stimulus
    at(1200);
    session.respond(); // valid, 200 ms
    at(2200); // stimulus
    at(2601);
    session.respond(); // valid, 401 ms: a lapse
    at(3601); // stimulus
    at(3651);
    session.respond(); // false start, 50 ms
    at(4000);
    session.respond(); // false start, nothing on screen
    at(5000); // stimulus, and nobody responds from here on:
    // time-outs at 35, 66, 97, 128 and 159 s; the stimulus of 160 s is still open at 180 s.

    at(179_999);
    expect(store.getState().biometrics).toEqual({ lastPvtMeanMs: null, lastPvtLapses: null });

    at(180_000);
    expect(recorded(session.state().trials)).toEqual([
      valid(200),
      valid(401, true),
      falseStart(50),
      falseStart(null),
      TIMEOUT,
      TIMEOUT,
      TIMEOUT,
      TIMEOUT,
      TIMEOUT,
    ]);
    const { lastPvtMeanMs, lastPvtLapses } = store.getState().biometrics;
    expect(lastPvtMeanMs).toBeCloseTo(300.5, 6); // (200 + 401) / 2: no time-out, no false start
    expect(lastPvtLapses).toBe(6); // one slow response and five time-outs
  });

  it("writes a null mean when there was no valid response", () => {
    const { session, store } = startPvt(0.5);
    at(180_000);
    expect(session.state().trials.some((trial) => trial.outcome === "valid")).toBe(false);
    expect(store.getState().biometrics).toEqual({ lastPvtMeanMs: null, lastPvtLapses: 5 });
  });
});
