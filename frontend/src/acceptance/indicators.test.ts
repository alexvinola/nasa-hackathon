/** G9 acceptance: the data rules of goals/G9-indicator-guides.md, checked on shared/indicators.json. */
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

const ROOT = resolve(__dirname, "../../..");
const json = (path: string) => JSON.parse(readFileSync(resolve(ROOT, path), "utf8"));

type Guide = {
  signal: string;
  label: string;
  how: { text: string; focus: string }[];
  why: string;
  whenAbnormal: { text: string; ruleIds: string[]; countermeasureIds: string[] };
  sources: string[];
};

const SIGNALS = [
  "selfReport.bloodPressure",
  "biometrics.heartRateBpm",
  "selfReport.glucoseMgDl",
  "selfReport.bodyTempC",
  "selfReport.sleepHoursLast24h",
  "selfReport.mood",
];
const NOT_JUDGED = "PULSAR does not judge this value yet: tell the crew medical officer";

const guides: Guide[] = json("shared/indicators.json").indicators;
const sources: Record<string, unknown> = json("shared/sources.json").sources;
const hrp = json("shared/hrp.json");
const rules: { id: string; signal: string; countermeasureId: string }[] = json("backend/assets/rules.json").rules;
const countermeasures: { id: string }[] = json("backend/assets/countermeasures.json").countermeasures;

const officialNames: string[] = [...Object.values(hrp.hazards), ...Object.values(hrp.risks)].map((entry) => (entry as { name: string }).name);
/** The engine's rules about one indicator: on the signal itself or on a field inside it (blood pressure). */
const rulesFor = (signal: string) => rules.filter((rule) => rule.signal === signal || rule.signal.startsWith(`${signal}.`));

describe("G9 indicator guides", () => {
  it("has exactly one guide for each of the six indicators", () => {
    expect(guides.map((guide) => guide.signal).sort()).toEqual([...SIGNALS].sort());
  });

  describe.each(SIGNALS)("%s", (signal) => {
    const guide = guides.find((candidate) => candidate.signal === signal)!;

    it("has numbered how-steps, a why and a what-to-do", () => {
      expect(guide.label.trim()).not.toBe("");
      expect(guide.how.length).toBeGreaterThanOrEqual(2);
      for (const step of guide.how) {
        expect(step.text.trim()).not.toBe("");
        expect(step.focus.trim()).not.toBe(""); // the part of the animation this step highlights
      }
      expect(guide.why.trim()).not.toBe("");
      expect(guide.whenAbnormal.text.trim()).not.toBe("");
    });

    it("cites at least one source registered in shared/sources.json", () => {
      expect(guide.sources.length).toBeGreaterThanOrEqual(1);
      for (const id of guide.sources) expect(sources, `unknown source ${id}`).toHaveProperty([id]);
    });

    it("names an HRP hazard or risk by its official name in `why`", () => {
      expect(officialNames.some((name) => guide.why.includes(name))).toBe(true);
    });

    it("quotes no threshold: it points at the engine's rules, or says the value is not judged", () => {
      // No figure at all in the two texts that could carry a range.
      expect(guide.why).not.toMatch(/\d/);
      expect(guide.whenAbnormal.text).not.toMatch(/\d/);

      const engineRules = rulesFor(signal);
      expect([...guide.whenAbnormal.ruleIds].sort()).toEqual(engineRules.map((rule) => rule.id).sort());
      expect([...guide.whenAbnormal.countermeasureIds].sort()).toEqual([...new Set(engineRules.map((rule) => rule.countermeasureId))].sort());
      for (const id of guide.whenAbnormal.countermeasureIds) {
        expect(countermeasures.some((countermeasure) => countermeasure.id === id), `unknown countermeasure ${id}`).toBe(true);
      }
      if (engineRules.length === 0) expect(guide.whenAbnormal.text).toContain(NOT_JUDGED);
      else expect(guide.whenAbnormal.text).not.toContain(NOT_JUDGED);
    });
  });
});
