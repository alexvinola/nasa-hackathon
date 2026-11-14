// Run: node --test frontend/src/modules/hud/reactionScore.test.mjs
import assert from "node:assert/strict";
import { test } from "node:test";
import { score } from "./reactionScore.ts";

const fast = (n) => Array(n).fill(250);

test("ten good reactions pass", () => {
  assert.deepEqual(score(fast(10)), { good: 10, meanMs: 250, passed: true });
});

test("one miss of ten is still 90 %: pass", () => {
  assert.equal(score([...fast(9), null]).passed, true);
});

test("two misses of ten fail", () => {
  assert.equal(score([...fast(8), null, null]).passed, false);
});

test("a lapse (355 ms) and an anticipation (under 100 ms) are not good reactions", () => {
  assert.deepEqual(score([...fast(8), 355, 99]), { good: 8, meanMs: 250, passed: false });
  assert.equal(score([...fast(9), 354]).good, 10);
});

test("an unfinished test never passes", () => {
  assert.equal(score(fast(9)).passed, false);
  assert.deepEqual(score([]), { good: 0, meanMs: null, passed: false });
});
