/**
 * G9 acceptance, data rules: shared/indicators.json holds one guide per health indicator the challenge names,
 * every guide is sourced, names an official HRP hazard or risk, and points at the engine's rules instead of
 * quoting ranges. Run with `make check-G9`.
 */
import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

const ROOT = new URL("../../../", import.meta.url);
const load = (path: string) => JSON.parse(readFileSync(new URL(path, ROOT), "utf-8"));

type Guide = {
  signal: string;
  label: string;
  how: string[];
  why: string;
  whenAbnormal: { ruleIds: string[]; countermeasureIds: string[]; note: string };
  sources: string[];
};
type Rule = { id: string; signal: string; countermeasureId: string };

const SIGNALS = [
  "selfReport.bloodPressure",
  "biometrics.heartRateBpm",
  "selfReport.glucoseMgDl",
  "selfReport.bodyTempC",
  "selfReport.sleepHoursLast24h",
  "selfReport.mood",
];
const NOT_JUDGED = "PULSAR does not judge this value yet: tell the crew medical officer";

const guides: Guide[] = load("shared/indicators.json").indicators;
const schema = load("shared/telemetry.schema.json");
const sources: Record<string, unknown> = load("shared/sources.json").sources;
const hrp = load("shared/hrp.json");
const rules: Rule[] = load("backend/assets/rules.json").rules;
const countermeasureIds: string[] = load("backend/assets/countermeasures.json").countermeasures.map((c: { id: string }) => c.id);
const officialNames: string[] = [...Object.values(hrp.hazards), ...Object.values(hrp.risks)].map((e) => (e as { name: string }).name);

const sorted = (list: string[]) => [...list].sort();

describe("G9 · shared/indicators.json", () => {
  it("has exactly one guide for each indicator the challenge names", () => {
    expect(sorted(guides.map((g) => g.signal))).toEqual(sorted(SIGNALS));
  });

  it("every signal is a field of the telemetry contract", () => {
    for (const { signal } of guides) {
      const [block, field] = signal.split(".");
      expect(schema.properties[block]?.properties?.[field], signal).toBeDefined();
    }
  });

  describe.each(guides)("$signal", (guide) => {
    const own = rules.filter((rule) => rule.signal === guide.signal);

    it("has a label, numbered steps, a why and a whenAbnormal", () => {
      expect(guide.label.trim()).not.toBe("");
      expect(guide.how.length).toBeGreaterThanOrEqual(2); // the array order is the numbering
      for (const step of guide.how) expect(step.trim()).not.toBe("");
      expect(guide.why.trim()).not.toBe("");
      expect(guide.whenAbnormal.note.trim()).not.toBe("");
    });

    it("cites at least one source, all registered in shared/sources.json", () => {
      expect(guide.sources.length).toBeGreaterThanOrEqual(1);
      for (const id of guide.sources) expect(sources[id], `unknown source ${id}`).toBeDefined();
    });

    it("why names an HRP hazard or risk with its official name", () => {
      expect(officialNames.some((name) => guide.why.includes(name)), guide.why).toBe(true);
    });

    it("whenAbnormal lists exactly the engine's rules for this signal and their countermeasures", () => {
      expect(sorted(guide.whenAbnormal.ruleIds)).toEqual(sorted(own.map((rule) => rule.id)));
      expect(sorted(guide.whenAbnormal.countermeasureIds)).toEqual(sorted([...new Set(own.map((rule) => rule.countermeasureId))]));
      for (const id of guide.whenAbnormal.countermeasureIds) expect(countermeasureIds).toContain(id);
    });

    it("says so when no rule judges the value, instead of giving a range", () => {
      if (own.length === 0) expect(guide.whenAbnormal.note).toContain(NOT_JUDGED);
      else expect(guide.whenAbnormal.note).not.toContain(NOT_JUDGED);
    });

    it("quotes no thresholds", () => {
      // No figures at all in why / whenAbnormal; the steps may count seconds, never a clinical value.
      expect(guide.why).not.toMatch(/\d/);
      expect(guide.whenAbnormal.note).not.toMatch(/\d/);
      for (const step of guide.how) expect(step).not.toMatch(/\d\s*(mmHg|mg\/dL|°\s*C|bpm)/i);
    });
  });
});
