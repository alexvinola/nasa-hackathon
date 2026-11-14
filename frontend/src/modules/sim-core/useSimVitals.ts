"use client";

import { useEffect, useState } from "react";
import type { Biometrics } from "@/modules/vision-hud/faceWorker";

/** One loop of the simulated shift, in seconds: rested, getting tired, exhausted, recovering. */
export const SIM_LOOP_S = 80;

/**
 * What the debug panel can force on top of the real readings:
 * "live" nothing (camera readings, or calm ones without a camera), "loop" the whole simulated shift again and
 * again, "rest" a false warning, "danger" a false danger.
 */
export type SimMode = "live" | "loop" | "rest" | "danger";

const unit = (value: number) => Math.min(1, Math.max(0, value));

/** How tired the simulated astronaut is, 0 rested to 1 exhausted, for each forced state. */
const TIRED: Record<Exclude<SimMode, "loop">, number> = { live: 0, rest: 0.75, danger: 1 };

/**
 * Simulated readings for a tiredness between 0 and 1, at second `t` (only the pulse depends on time). Nothing here
 * is measured: it exists so the whole chain (readings, rules engine, alarm, what PULSAR says) can run and be shown
 * without a camera or a heart-rate sensor. The engine's drowsiness rule (PERCLOS at or above 0.11) holds from a
 * tiredness of about 0.54 and its exhaustion rule (fatigue score at or above 0.70) from 0.85. Rested PERCLOS is
 * 0.03, the mean of the alert windows of RLDD (data/out/fatigue_report.md).
 */
export function simVitals(tired: number, t: number): Biometrics {
  // No jitter on the two signals the engine has rules for: hovering around a threshold would flip the verdict
  // back and forth, and every flip costs a model call to phrase it.
  return {
    heartRateBpm: Math.round(66 + tired * 12 + Math.sin(t * 0.35) * 3),
    heartRateConfidence: 0, // the contract's way of saying "do not trust this as a measurement"
    fatigueScore: unit(0.15 + tired * 0.65),
    perclos: unit(0.03 + tired * 0.15),
    yawnsPerMin: Math.round(tired * 3),
    postureStability: unit(0.94 - tired * 0.2),
    armAsymmetry: 0.08,
    lastPvtMeanMs: null,
    lastPvtLapses: null,
  };
}

/** Tiredness along the looped shift: flat for 20 s, climbs for 20 s, holds for 20 s, recovers in 15 s. */
export function loopTiredness(t: number): number {
  const s = t % SIM_LOOP_S;
  return s < 20 ? 0 : s < 40 ? (s - 20) / 20 : s < 60 ? 1 : s < 75 ? 1 - (s - 60) / 15 : 0;
}

/** Simulated cabin CO2 in mmHg: a slow swing that stays under the engine's limit (it is here to be watched). */
export const simCabinCo2 = (t: number) => Math.round((3 + 0.4 * Math.sin(t / 20)) * 10) / 10;

/** The simulated readings for `mode`, refreshed twice a second. */
export function useSimVitals(mode: SimMode): { vitals: Biometrics; cabinCo2: number } {
  const [t, setT] = useState(0);
  useEffect(() => {
    const started = performance.now();
    const id = setInterval(() => setT((performance.now() - started) / 1000), 500);
    return () => clearInterval(id);
  }, [mode]); // a looped shift starts from the beginning each time it is switched on
  return { vitals: simVitals(mode === "loop" ? loopTiredness(t) : TIRED[mode], t), cabinCo2: simCabinCo2(t) };
}
