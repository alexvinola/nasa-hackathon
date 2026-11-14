/** Eyes held closed: what the worker adds to `fatigueScore` when someone falls asleep in front of the camera. */

import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import { CLOSURE_HOLD_S, SustainedClosure } from "./sleep";

const FPS = 15;

/** Feeds (state, seconds) stretches at 15 fps and returns the detector and the time of the last frame. */
function run(...stretches: [boolean | null, number][]): [SustainedClosure, number] {
  const closure = new SustainedClosure();
  let frame = 0;
  for (const [state, seconds] of stretches) {
    for (let i = 0; i < Math.round(seconds * FPS); i++) closure.push(frame++ / FPS, state);
  }
  return [closure, (frame - 1) / FPS];
}

describe("SustainedClosure", () => {
  it("scores nothing for blinks", () => {
    const [closure, at] = run([false, 2], [true, 0.3], [false, 1], [true, 0.8], [false, 0.2]);
    expect(closure.score(at)).toBe(0);
  });

  it("crosses the engine's fatigue threshold after about three seconds of closed eyes", () => {
    const rules = JSON.parse(readFileSync(resolve(__dirname, "../../../../backend/assets/rules.json"), "utf8")).rules;
    const threshold = rules.find((r: { id: string }) => r.id === "fatigue-score-high").threshold;
    const [before, t1] = run([false, 60], [true, 2.9]);
    expect(before.score(t1)).toBeLessThan(threshold);
    const [after, t2] = run([false, 60], [true, 3.3]);
    expect(after.score(t2)).toBeGreaterThanOrEqual(threshold);
    const [long, t3] = run([false, 60], [true, 6]);
    expect(long.score(t3)).toBe(1);
  });

  it("holds the score after the eyes open, then lets it go", () => {
    const [closure, at] = run([true, 5], [false, 1]);
    expect(closure.score(at)).toBe(1);
    expect(closure.score(at + CLOSURE_HOLD_S)).toBe(0);
  });

  it("bridges a face lost for a moment and ends the closure when it is lost for longer", () => {
    const [bridged, t1] = run([true, 2], [null, 0.13], [true, 2]);
    expect(bridged.score(t1)).toBe(1);
    const [broken, t2] = run([true, 2], [null, 1], [true, 0.5]);
    expect(broken.score(t2)).toBeLessThan(0.4);
  });

  it("starts again from nothing after a reset", () => {
    const [closure, at] = run([true, 5]);
    closure.reset();
    expect(closure.score(at)).toBe(0);
  });
});
