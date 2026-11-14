/**
 * G9 acceptance, UI: one click on an indicator of the body twin opens its guide, with the current value, the
 * engine's status for it and the line "Not a medical device". The rules engine is mocked from shared/scenarios/:
 * the scenario's `input` goes into the store (window.__synapse, test mode only) and POST /rules/evaluate answers
 * with the scenario's `expect`. Run with `make check-G9`.
 */
import { readdirSync, readFileSync } from "node:fs";
import path from "node:path";
import { expect, test, type Page } from "@playwright/test";

const ROOT = path.resolve(__dirname, "../../..");
const load = (file: string) => JSON.parse(readFileSync(path.join(ROOT, file), "utf-8"));

type Scenario = {
  name: string;
  input: Record<string, Record<string, unknown>>;
  expect: { status: string; escalation: string; hrpRisk: string | null; affectedSystems: string[]; factorSignals: string[] };
};
type Guide = { signal: string; label: string; how: string[]; why: string; whenAbnormal: { countermeasureIds: string[]; note: string } };
type Rule = { signal: string; status: string };
type Countermeasure = { id: string; title: string; steps: string[] };

const guides: Guide[] = load("shared/indicators.json").indicators;
const rules: Rule[] = load("backend/assets/rules.json").rules;
const countermeasures: Countermeasure[] = load("backend/assets/countermeasures.json").countermeasures;
const scenarios: Scenario[] = readdirSync(path.join(ROOT, "shared/scenarios"))
  .filter((file) => file.endsWith(".json"))
  .sort()
  .map((file) => load(`shared/scenarios/${file}`));

const valueOf = (scenario: Scenario, signal: string) => {
  const [block, field] = signal.split(".");
  return scenario.input[block][field];
};

/** What the engine says about one indicator: flagged with its rule's status, fine, not read, or not judged at all. */
function statusOf(scenario: Scenario, signal: string): string {
  const own = rules.filter((rule) => rule.signal === signal);
  if (own.length === 0) return "NOT_JUDGED";
  if (scenario.expect.factorSignals.includes(signal)) return own.some((rule) => rule.status === "RED") ? "RED" : "AMBER";
  return valueOf(scenario, signal) == null ? "NO_READING" : "GREEN";
}

/** The decision the engine would return for the scenario, built from its `expect`. */
const decisionOf = (scenario: Scenario) => ({
  status: scenario.expect.status,
  escalation: scenario.expect.escalation,
  affectedSystems: scenario.expect.affectedSystems,
  hrpRisk: scenario.expect.hrpRisk,
  factors: scenario.expect.factorSignals.map((signal) => ({
    signal,
    value: valueOf(scenario, signal),
    threshold: null,
    hazard: null,
    source: null,
    message: signal,
  })),
  countermeasureId: null,
});

/** Opens the HUD with the backend mocked and the scenario loaded into the store. */
async function openWith(page: Page, scenario: Scenario) {
  const json = (body: unknown) => ({ contentType: "application/json", body: JSON.stringify(body) });
  await page.route("http://localhost:8000/**", (route) => route.fulfill({ status: 503 })); // nothing else is up
  await page.route("**/rules", (route) => route.fulfill(json(rules)));
  await page.route("**/countermeasures", (route) => route.fulfill(json(countermeasures)));
  await page.route("**/rules/evaluate", (route) => route.fulfill(json(decisionOf(scenario))));
  await page.goto("/");
  await page.waitForFunction(() => "__synapse" in window);
  await page.evaluate((input) => (window as any).__synapse.getState().setTelemetry(input), scenario.input);
}

const twin = (page: Page) => page.getByTestId("body-twin");
const guidePanel = (page: Page) => page.getByTestId("indicator-guide");

test("the twin shows the six indicators of the challenge", async ({ page }) => {
  await openWith(page, scenarios[0]);
  await expect(twin(page).locator("[data-indicator]")).toHaveCount(guides.length);
  for (const guide of guides) await expect(twin(page).locator(`[data-indicator="${guide.signal}"]`)).toBeVisible();
});

for (const scenario of scenarios) {
  test(`${scenario.name}: one click opens each guide with its value and the engine's status`, async ({ page }) => {
    await openWith(page, scenario);

    for (const guide of guides) {
      const status = statusOf(scenario, guide.signal);
      const value = valueOf(scenario, guide.signal);
      await expect(twin(page).locator(`[data-indicator="${guide.signal}"]`)).toHaveAttribute("data-status", status);

      await twin(page).locator(`[data-indicator="${guide.signal}"]`).click(); // the one click
      const panel = guidePanel(page);
      await expect(panel).toBeVisible();
      await expect(panel).toHaveAttribute("data-signal", guide.signal);
      await expect(panel).toHaveAttribute("data-status", status);
      await expect(panel).toContainText(guide.label);

      const shown = panel.getByTestId("guide-value");
      if (value == null) await expect(shown).toContainText(/no reading/i);
      else await expect(shown).toContainText(String(value));

      // how (numbered steps), why, what to do
      await expect(panel.locator("ol[data-testid='guide-how'] > li")).toHaveText(guide.how);
      await expect(panel).toContainText(guide.why);
      await expect(panel).toContainText(guide.whenAbnormal.note);
      for (const id of guide.whenAbnormal.countermeasureIds) {
        const countermeasure = countermeasures.find((c) => c.id === id)!;
        for (const step of countermeasure.steps) await expect(panel).toContainText(step);
      }
      await expect(panel).toContainText(/not a medical device/i);
    }
  });
}
