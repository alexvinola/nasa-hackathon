/** The G9 indicator guides (shared/indicators.json) and what the HUD shows next to them. */
import data from "../../../../shared/indicators.json";
import { INDICATORS_ES } from "./indicators.es";
import { t, type Lang } from "@/i18n";
import type { Decision, Rule, Status, Telemetry } from "@/modules/voice-ai/verdictApi";

export type Guide = {
  signal: string;
  label: string;
  instrument: string;
  how: { text: string; focus: string }[];
  why: string;
  whenAbnormal: { text: string; ruleIds: string[]; countermeasureIds: string[] };
  sources: string[];
  /** Set when the how-steps are team wording, not taken from a source. */
  assumption: string | null;
};
export const GUIDES: Guide[] = data.indicators;

/** The guide in `lang`: the JSON is the English original; Spanish text comes from indicators.es.ts (rule ids, focus and sources stay). */
export function localizedGuide(guide: Guide, lang: Lang): Guide {
  const es = lang === "es" ? INDICATORS_ES[guide.signal] : undefined;
  if (!es) return guide;
  return {
    ...guide,
    label: es.label,
    instrument: es.instrument,
    how: guide.how.map((step, index) => ({ ...step, text: es.how[index] ?? step.text })),
    why: es.why,
    whenAbnormal: { ...guide.whenAbnormal, text: es.whenAbnormal },
  };
}

/** What the guide shows as the engine's status: one of the engine's own, or why there is none. */
export type GuideStatus = Status | "NOT JUDGED" | "WAITING";

const UNIT: Record<string, string> = {
  "biometrics.heartRateBpm": "bpm",
  "selfReport.glucoseMgDl": "mg/dL",
  "selfReport.bodyTempC": "°C",
  "selfReport.sleepHoursLast24h": "h",
  "selfReport.mood": "/ 5",
};

/** The indicator's current value as text, read from the telemetry the HUD sends to the engine. */
export function currentValue(signal: string, telemetry: Telemetry): string {
  const value = signal.split(".").reduce<unknown>((node, key) => (node as Record<string, unknown> | null)?.[key], telemetry);
  if (value == null) return t("guides.value.none");
  if (typeof value === "object") {
    const { systolic, diastolic } = value as { systolic: number; diastolic: number };
    return `${systolic}/${diastolic} mmHg`;
  }
  return `${value} ${UNIT[signal] ?? ""}`.trim();
}

const SEVERITY: Status[] = ["GREEN", "AMBER", "RED"];

/**
 * The status the rules engine gives one indicator. Never decided here: no rule means "NOT JUDGED", a rule that did
 * not trigger means GREEN, and a triggered one carries the status the engine's own rule list (GET /rules) gives it.
 */
export function statusOf(guide: Guide, decision: Decision | null, rules: Rule[]): GuideStatus {
  if (guide.whenAbnormal.ruleIds.length === 0) return "NOT JUDGED";
  if (!decision) return "WAITING";
  if (!decision.factors.some((factor) => factor.signal === guide.signal || factor.signal.startsWith(`${guide.signal}.`))) return "GREEN";
  // shortcut: a factor does not say which rule fired, so this takes the most severe rule of the indicator; exact
  // while each indicator has one rule, upgrade when the engine reports the rule id per factor.
  const statuses = rules.filter((rule) => guide.whenAbnormal.ruleIds.includes(rule.id)).map((rule) => rule.status);
  return statuses.sort((a, b) => SEVERITY.indexOf(b) - SEVERITY.indexOf(a))[0] ?? "WAITING"; // rule list not loaded yet: never borrow the overall status
}
