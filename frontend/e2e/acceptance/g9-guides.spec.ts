/**
 * G9 acceptance: one click on the twin or on a HUD reading opens the indicator's guide, with the current value,
 * the status the rules engine gives it and the line "Not a medical device". The engine is mocked from
 * shared/scenarios/; nothing here reaches a real backend.
 */
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { expect, test, type Page } from "@playwright/test";

const ROOT = resolve(__dirname, "../../..");
const json = (path: string) => JSON.parse(readFileSync(resolve(ROOT, path), "utf8"));

type Guide = { signal: string; how: { text: string; focus: string }[] };
type Rule = { id: string; signal: string; threshold: number; status: string; hazard: string | null; source: string | null; countermeasureId: string; message: string };

const guides: Guide[] = json("shared/indicators.json").indicators;
const rules: Rule[] = json("backend/assets/rules.json").rules;
const countermeasures: { id: string }[] = json("backend/assets/countermeasures.json").countermeasures;

const API = "http://localhost:8000";
const CORS = { "access-control-allow-origin": "*", "access-control-allow-headers": "*", "access-control-allow-methods": "*" };

/** The backend answers what the scenario expects of the engine, whatever telemetry the HUD sends. */
async function mockEngine(page: Page, scenarioFile: string) {
  const scenario = json(`shared/scenarios/${scenarioFile}`);
  const at = (path: string) => path.split(".").reduce((node, key) => node?.[key], scenario.input);
  const triggered = (scenario.expect.factorSignals as string[]).map((signal) => rules.find((rule) => rule.signal === signal)!);
  const decision = {
    status: scenario.expect.status,
    escalation: scenario.expect.escalation,
    affectedSystems: scenario.expect.affectedSystems,
    hrpRisk: scenario.expect.hrpRisk,
    factors: triggered.map((rule) => ({ signal: rule.signal, value: at(rule.signal), threshold: rule.threshold, hazard: rule.hazard, source: rule.source, message: rule.message })),
    countermeasureId: triggered[0]?.countermeasureId ?? null,
  };
  await page.route(`${API}/**`, (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    const reply = (body: unknown) => route.fulfill({ status: 200, headers: CORS, contentType: "application/json", body: JSON.stringify(body) });
    if (request.method() === "OPTIONS") return route.fulfill({ status: 204, headers: CORS });
    if (path === "/rules/evaluate") return reply(decision);
    if (path === "/voice/advise") return reply({ decision, say: "", source: "fallback" });
    if (path === "/rules") return reply(rules);
    if (path.startsWith("/countermeasures/")) return reply(countermeasures.find((countermeasure) => path.endsWith(`/${countermeasure.id}`)));
    return route.fulfill({ status: 503, headers: CORS }); // voice, vision: not part of this goal
  });
}

const guideOf = (page: Page, signal: string) => page.locator(`[data-guide="${signal}"]`);
const NOT_JUDGED = "PULSAR does not judge this value yet: tell the crew medical officer";

test("each marker on the twin opens its guide in one click", async ({ page }) => {
  await mockEngine(page, "01-nominal.json");
  await page.goto("/");
  expect(guides).toHaveLength(6);
  for (const guide of guides) {
    await page.locator(`[data-twin] [data-indicator="${guide.signal}"]`).click();
    const panel = guideOf(page, guide.signal);
    await expect(panel).toBeVisible();
    await expect(panel).toHaveAttribute("data-hud-panel", /.*/); // the mascot must not park over it
    await expect(panel).toContainText(/not a medical device/i);
    await expect(panel.locator("[data-guide-value]")).not.toBeEmpty();
    await expect(panel.locator("[data-guide-status]")).not.toBeEmpty();
    await expect(panel.locator("[data-guide-step]")).toHaveCount(guide.how.length);
    await expect(panel.locator("[data-guide-animation]")).toBeVisible();
    await expect(page.locator("[data-guide]")).toHaveCount(1); // one guide at a time
  }
});

test("the HUD heart-rate reading opens its guide with the current value", async ({ page }) => {
  await mockEngine(page, "01-nominal.json");
  await page.goto("/");
  await page.locator('[data-reading="biometrics.heartRateBpm"]').click();
  const panel = guideOf(page, "biometrics.heartRateBpm");
  await expect(panel).toBeVisible();
  await expect(panel.locator("[data-guide-value]")).toHaveText(/\d+\s*bpm/i);
  // The engine has no rule on the pulse: the guide says so instead of giving a range.
  await expect(panel).toContainText(NOT_JUDGED);
  await expect(panel.locator("[data-guide-status]")).toHaveText(/not judged/i);
});

for (const [scenarioFile, flagged, clear] of [
  ["02-short-sleep.json", "selfReport.sleepHoursLast24h", "selfReport.mood"],
  ["05-low-mood.json", "selfReport.mood", "selfReport.sleepHoursLast24h"],
] as const) {
  test(`the guide shows the engine's status for the indicator (${scenarioFile})`, async ({ page }) => {
    await mockEngine(page, scenarioFile);
    await page.goto("/");
    const ruleStatus = rules.find((rule) => rule.signal === flagged)!.status;

    await page.locator(`[data-twin] [data-indicator="${flagged}"]`).click();
    await expect(guideOf(page, flagged).locator("[data-guide-status]")).toHaveText(new RegExp(ruleStatus, "i"), { timeout: 15_000 });

    await page.locator(`[data-twin] [data-indicator="${clear}"]`).click();
    await expect(guideOf(page, clear).locator("[data-guide-status]")).toHaveText(/green/i, { timeout: 15_000 });
  });
}

test("each how-step highlights its part of the animation", async ({ page }) => {
  await mockEngine(page, "01-nominal.json");
  await page.goto("/");
  for (const guide of guides) {
    await page.locator(`[data-twin] [data-indicator="${guide.signal}"]`).click();
    const panel = guideOf(page, guide.signal);
    for (const [index, step] of guide.how.entries()) {
      await panel.locator("[data-guide-step]").nth(index).click();
      await expect(panel.locator("[data-guide-step]").nth(index)).toHaveAttribute("aria-current", "step");
      await expect(panel.locator("[data-guide-animation]")).toHaveAttribute("data-focus", step.focus);
    }
  }
});

test("the guide closes and respects reduced motion", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await mockEngine(page, "01-nominal.json");
  await page.goto("/");
  await page.locator('[data-twin] [data-indicator="selfReport.bodyTempC"]').click();
  const panel = guideOf(page, "selfReport.bodyTempC");
  await expect(panel.locator("[data-guide-animation]")).toHaveAttribute("data-motion", "still");
  await panel.getByRole("button", { name: /close/i }).click();
  await expect(page.locator("[data-guide]")).toHaveCount(0);
});
