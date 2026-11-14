/** The indicator guides (shared/indicators.json) and what the twin shows for each: its reading and the engine's status. */
import data from "../../../../shared/indicators.json";
import type { Decision, Status, Telemetry } from "@/modules/voice-ai/verdictApi";
import type { Rule } from "./rulebook";

export type Guide = {
  signal: string;
  label: string;
  unit: string;
  method: string;
  how: string[];
  why: string;
  whenAbnormal: { ruleIds: string[]; countermeasureIds: string[]; note: string };
  sources: string[];
  assumption: string;
};

export const GUIDES = data.indicators as Guide[];
export const NOTICE = data.notice;

/**
 * What the engine says about one indicator: its verdict when a rule judges it, NO_READING when there is no value,
 * NOT_JUDGED when no rule looks at it, UNKNOWN when the engine is not answering.
 */
export type IndicatorStatus = Status | "NO_READING" | "NOT_JUDGED" | "UNKNOWN";
/** A body-system zone: the engine's status for it, or UNKNOWN before the first verdict. */
export type ZoneStatus = Status | "UNKNOWN";

export const STATUS_LABEL: Record<IndicatorStatus, string> = {
  GREEN: "ENGINE · GREEN",
  AMBER: "ENGINE · AMBER",
  RED: "ENGINE · RED",
  NO_READING: "NO READING",
  NOT_JUDGED: "NOT JUDGED BY PULSAR",
  UNKNOWN: "ENGINE NOT ANSWERING",
};
export const STATUS_COLOR: Record<IndicatorStatus, string> = {
  GREEN: "#34d399",
  AMBER: "#fbbf24",
  RED: "#ef4444",
  NO_READING: "rgb(238 241 251 / 0.45)",
  NOT_JUDGED: "#9a8cff",
  UNKNOWN: "rgb(238 241 251 / 0.45)",
};

/** The value of a contract field such as `selfReport.mood`; null when there is no telemetry or no reading. */
export function readingOf(telemetry: Telemetry | null, signal: string): unknown {
  const [block, field] = signal.split(".");
  return (telemetry as Record<string, Record<string, unknown>> | null)?.[block]?.[field] ?? null;
}

/** The reading with its unit; null when there is none. Blood pressure is the one reading with two numbers. */
export function formatReading(value: unknown, unit: string): string | null {
  if (value == null) return null;
  if (typeof value === "object") {
    const { systolic, diastolic } = value as { systolic: number; diastolic: number };
    return `${systolic}/${diastolic} ${unit}`;
  }
  return `${value} ${unit}`;
}

const worst = (statuses: Status[], fallback: Status): Status =>
  statuses.includes("RED") ? "RED" : statuses.includes("AMBER") ? "AMBER" : fallback;

/** No threshold is compared here: a flagged indicator is one the engine lists among the decision's factors. */
export function statusOf(guide: Guide, value: unknown, decision: Decision | null, rules: Rule[] | null): IndicatorStatus {
  if (guide.whenAbnormal.ruleIds.length === 0) return "NOT_JUDGED";
  if (value == null) return "NO_READING";
  if (!decision) return "UNKNOWN";
  if (!decision.factors.some((factor) => factor.signal === guide.signal)) return "GREEN";
  // Flagged. Its severity is its rule's; until the engine has listed its rules, the verdict's is all there is.
  const own = (rules ?? []).filter((rule) => guide.whenAbnormal.ruleIds.includes(rule.id));
  return worst(own.map((rule) => rule.status), decision.status);
}

/** The status of one body-system zone: the worst triggered rule that names it, GREEN when none does. */
export function zoneStatus(system: string, decision: Decision | null, rules: Rule[] | null): ZoneStatus {
  if (!decision) return "UNKNOWN";
  if (!decision.affectedSystems.includes(system)) return "GREEN";
  const flagged = new Set(decision.factors.map((factor) => factor.signal));
  const triggered = (rules ?? []).filter((rule) => flagged.has(rule.signal) && rule.bodySystems.includes(system));
  return worst(triggered.map((rule) => rule.status), decision.status);
}
