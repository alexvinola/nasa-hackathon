// Run: node --test frontend/src/modules/hud/reactionScore.test.mjs
import assert from "node:assert/strict";
import { test } from "node:test";
import { TRIALS, score } from "./reactionScore.ts";

const fast = (n) => Array(n).fill(250);

test("the test is three stimuli", () => {
  assert.equal(TRIALS, 3);
});

test("three good reactions pass", () => {
  assert.deepEqual(score(fast(3)), { good: 3, meanMs: 250, passed: true });
});

test("one miss of three is below 90 %: fail", () => {
  assert.equal(score([...fast(2), null]).passed, false);
});

test("a lapse (355 ms) and an anticipation (under 100 ms) are not good reactions", () => {
  assert.deepEqual(score([250, 355, 99]), { good: 1, meanMs: 250, passed: false });
  assert.equal(score([...fast(2), 354]).good, 3);
});

test("an unfinished test never passes", () => {
  assert.equal(score(fast(2)).passed, false);
  assert.deepEqual(score([]), { good: 0, meanMs: null, passed: false });
});
