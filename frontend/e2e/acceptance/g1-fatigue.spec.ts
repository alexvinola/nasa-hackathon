/**
 * G1 acceptance: MediaPipe in the Web Worker turns a face on the camera into `biometrics.fatigueScore`.
 *
 * Chromium's fake camera plays a recorded fixture instead of the webcam (goals/G1-camera-fatigue.md): eyes kept
 * closed must push the score over 0.7 within 5 s, an alert face must keep it under 0.4 for 10 s, and the worker
 * must keep up 15 readings a second. The clock starts at the first reading, once the models are loaded and the
 * camera is live. useFaceMetrics hands every reading to `window.__pulsarBiometrics` for tests; nothing here reaches
 * a backend (every call to it fails, and the HUD must keep working).
 */
import { existsSync } from "node:fs";
import { resolve } from "node:path";
import { expect, test, type Page, type PlaywrightWorkerArgs } from "@playwright/test";

const ROOT = resolve(__dirname, "../../..");
const FIXTURE = (name: string) => resolve(ROOT, "data/fixtures", name);

const FPS = 15;
const JITTER = 0.95; // the hook paces the worker at 15 fps: allow 5% for timer jitter over the measuring window

type Reading = { at: number; fatigueScore: number };

/** Records every reading the worker hands to the HUD, with the time it arrived. Runs in the browser. */
function recordReadings() {
  const readings: Reading[] = [];
  (window as unknown as { __g1: Reading[] }).__g1 = readings;
  let current: { fatigueScore: number } | undefined;
  Object.defineProperty(window, "__pulsarBiometrics", {
    configurable: true,
    get: () => current,
    set: (value: { fatigueScore: number }) => {
      current = value;
      readings.push({ at: performance.now(), fatigueScore: value.fatigueScore });
    },
  });
}

/** Opens the HUD in a Chromium whose fake camera plays `fixture`; each fixture needs its own browser. */
async function withCamera<T>(playwright: PlaywrightWorkerArgs["playwright"], baseURL: string | undefined, fixture: string, run: (page: Page) => Promise<T>) {
  const browser = await playwright.chromium.launch({
    args: ["--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream", `--use-file-for-fake-video-capture=${FIXTURE(fixture)}`],
  });
  try {
    return await run(await browser.newPage({ baseURL }));
  } finally {
    await browser.close();
  }
}

async function watch(page: Page, seconds: number) {
  await page.route("http://localhost:8000/**", (route) => route.fulfill({ status: 503 }));
  await page.addInitScript(recordReadings);
  await page.goto("/pulsar");
  // Model download and camera start are not part of the 5 s: the clock starts at the first reading.
  await page.waitForFunction(() => (window as unknown as { __g1: Reading[] }).__g1.length > 0, null, { timeout: 60_000 });
  await page.waitForTimeout(seconds * 1000);
  const readings = await page.evaluate(() => (window as unknown as { __g1: Reading[] }).__g1);
  const start = readings[0].at;
  return readings.map((r) => ({ t: (r.at - start) / 1000, score: r.fatigueScore }));
}

function fps(readings: { t: number }[]) {
  const last = readings[readings.length - 1].t;
  return (readings.length - 1) / last;
}

for (const name of ["eyes_closed.y4m", "alert.y4m"]) {
  test(`fixture ${name} exists`, () => {
    expect(existsSync(FIXTURE(name)), `record it first: see goals/G1-camera-fatigue.md`).toBe(true);
  });
}

test("eyes closed: fatigueScore goes over 0.7 in under 5 s, at 15 fps or more", async ({ playwright, baseURL }) => {
  const readings = await withCamera(playwright, baseURL, "eyes_closed.y4m", (page) => watch(page, 6));
  const over = readings.find((r) => r.score > 0.7);
  const rate = fps(readings);
  console.log(`eyes_closed: first reading over 0.7 at ${over ? over.t.toFixed(2) : "never"} s, ${rate.toFixed(1)} readings/s`);
  expect(over, "fatigueScore never went over 0.7").toBeDefined();
  expect(over!.t).toBeLessThan(5);
  expect(rate).toBeGreaterThanOrEqual(FPS * JITTER);
});

test("alert: fatigueScore stays under 0.4 for 10 s, at 15 fps or more", async ({ playwright, baseURL }) => {
  // Half a second of slack so the last reading lands past 10 s.
  const readings = await withCamera(playwright, baseURL, "alert.y4m", (page) => watch(page, 10.5));
  const worst = Math.max(...readings.map((r) => r.score));
  const rate = fps(readings);
  console.log(`alert: highest fatigueScore ${worst.toFixed(3)} over ${readings.at(-1)!.t.toFixed(1)} s, ${rate.toFixed(1)} readings/s`);
  expect(readings.at(-1)!.t).toBeGreaterThanOrEqual(10);
  expect(worst).toBeLessThan(0.4);
  expect(rate).toBeGreaterThanOrEqual(FPS * JITTER);
});
