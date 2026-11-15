/**
 * The measurements the astronaut takes with a device and types in: what each field accepts and how the entries
 * become the `selfReport` block (and the pulse) of the telemetry the rules engine reads.
 *
 * The accepted ranges are the contract's own (shared/telemetry.schema.json): what the contract can carry, not what is
 * healthy. Nothing here judges a value: that is the rules engine's job, and an indicator with no rule stays not judged.
 */
import schema from "../../../../shared/telemetry.schema.json";
import type { Telemetry } from "@/modules/voice-ai/verdictApi";

export type Field = {
  key: string; // the entry's name: one per number typed; its label is the message `selfReport.field.<key>`
  unit: string; // shown as is, or a message key when the unit is a word (`selfReport.unit.*`)
  min: number;
  max: number;
  step: number; // what the arrow keys and the +/- buttons move by
};

type Bounds = { minimum: number; maximum: number };
const self = schema.properties.selfReport.properties;
const pressure = self.bloodPressure.oneOf[1].properties as { systolic: Bounds; diastolic: Bounds };
const field = (key: string, unit: string, bounds: Bounds, step: number): Field => ({
  key,
  unit,
  min: bounds.minimum,
  max: bounds.maximum,
  step,
});

/** The fields of each indicator, by contract signal, in the order the form asks for them. */
export const FIELDS: Record<string, Field[]> = {
  "biometrics.heartRateBpm": [field("heartRateBpm", "selfReport.unit.bpm", schema.properties.biometrics.properties.heartRateBpm as Bounds, 1)],
  "selfReport.bloodPressure": [
    field("systolic", "mmHg", pressure.systolic, 1),
    field("diastolic", "mmHg", pressure.diastolic, 1),
  ],
  "selfReport.glucoseMgDl": [field("glucoseMgDl", "mg/dL", self.glucoseMgDl as Bounds, 1)],
  "selfReport.bodyTempC": [field("bodyTempC", "°C", self.bodyTempC as Bounds, 0.1)],
  "selfReport.sleepHoursLast24h": [field("sleepHoursLast24h", "h", self.sleepHoursLast24h as Bounds, 0.5)],
  "selfReport.mood": [field("mood", "selfReport.unit.ofFive", self.mood as Bounds, 1)],
};

/**
 * What an official source says is usual for each measurement, shown beside the field so the astronaut has something
 * to compare with. It is a reference, never a verdict: no rule reads it and the form does not colour a value by it.
 * `text` is a message key (i18n/messages/selfReport.ts) that carries the numbers; `source` is an id in
 * shared/sources.json. `flight` says whether the source is about spaceflight: NASA gives a figure for sleep and for
 * temperature only, and the rest are adults on Earth, where microgravity may shift what is usual.
 */
export type Reference = { text: string; source: string; flight: boolean };
export const REFERENCES: Record<string, Reference[]> = {
  "biometrics.heartRateBpm": [{ text: "selfReport.ref.pulse", source: "medlineplus-pulse", flight: false }],
  "selfReport.bloodPressure": [{ text: "selfReport.ref.pressure", source: "medlineplus-high-blood-pressure", flight: false }],
  "selfReport.glucoseMgDl": [{ text: "selfReport.ref.glucose", source: "medlineplus-blood-sugar-test", flight: false }],
  "selfReport.bodyTempC": [
    { text: "selfReport.ref.tempNasa", source: "nasa-std-3001-vol1", flight: true },
    { text: "selfReport.ref.temp", source: "medlineplus-body-temperature-norms", flight: false },
  ],
  "selfReport.sleepHoursLast24h": [{ text: "selfReport.ref.sleep", source: "nasa-std-3001-vol1", flight: true }],
  "selfReport.mood": [],
};

/** What has been typed in so far: one number per field key. An indicator counts once all its fields are there. */
export type Entries = Record<string, number>;

export const isValid = (f: Field, value: number) => Number.isFinite(value) && value >= f.min && value <= f.max;

/** Whether every field of an indicator has been entered. */
export const entered = (signal: string, entries: Entries) => FIELDS[signal].every((f) => f.key in entries);

/** The telemetry with the typed measurements in place of the example's. An indicator not entered is left as it was. */
export function withEntries(telemetry: Telemetry, entries: Entries): Telemetry {
  const has = (signal: string) => entered(signal, entries);
  const selfReport = {
    ...telemetry.selfReport,
    ...(has("selfReport.sleepHoursLast24h") ? { sleepHoursLast24h: entries.sleepHoursLast24h } : {}),
    ...(has("selfReport.mood") ? { mood: entries.mood } : {}),
    ...(has("selfReport.glucoseMgDl") ? { glucoseMgDl: entries.glucoseMgDl } : {}),
    ...(has("selfReport.bodyTempC") ? { bodyTempC: entries.bodyTempC } : {}),
    ...(has("selfReport.bloodPressure") ? { bloodPressure: { systolic: entries.systolic, diastolic: entries.diastolic } } : {}),
  };
  // A pulse counted by hand is a measurement: full confidence, unlike the simulated one it replaces.
  const biometrics = has("biometrics.heartRateBpm")
    ? { ...telemetry.biometrics, heartRateBpm: entries.heartRateBpm, heartRateConfidence: 1 }
    : telemetry.biometrics;
  return { ...telemetry, selfReport, biometrics } as Telemetry;
}
