"use client";

import type { Biometrics } from "@/modules/vision-hud/faceWorker";
import { useVerdict } from "./useVerdict";
import type { Status } from "./verdictApi";

const LIGHT: Record<Status, string> = {
  GREEN: "bg-emerald-400 shadow-[0_0_12px] shadow-emerald-400",
  AMBER: "bg-amber-400 shadow-[0_0_12px] shadow-amber-400",
  RED: "bg-red-500 shadow-[0_0_12px] shadow-red-500 animate-pulse",
};
const ESCALATION = { SELF_CARE: "SELF-CARE", CREW: "TELL THE CREW", FLIGHT_SURGEON: "FLIGHT SURGEON" } as const;

/** The rules engine's verdict over the HUD: traffic light, escalation, why, and what PULSAR said. */
export function VerdictPanel({ biometrics }: { biometrics: Biometrics | null }) {
  const { decision, advice, error } = useVerdict(biometrics);

  return (
    <section className="pointer-events-none absolute right-8 top-20 w-80 rounded-lg border border-pulse/30 bg-space/70 p-4 text-[11px] tracking-[0.12em] text-shell/80 backdrop-blur">
      <header className="flex items-center gap-3">
        <span className={`h-3 w-3 rounded-full ${decision ? LIGHT[decision.status] : "bg-orbit/40"}`} />
        <span className="text-pulse">{decision ? decision.status : "WAITING FOR THE CAMERA"}</span>
        {decision && <span className="ml-auto text-orbit">{ESCALATION[decision.escalation]}</span>}
      </header>

      {biometrics && (
        <dl className="mt-3 grid grid-cols-3 gap-2 text-[10px] text-shell/60">
          <div><dt>PERCLOS</dt><dd className="text-shell">{Math.round(biometrics.perclos * 100)}%</dd></div>
          <div><dt>FATIGUE</dt><dd className="text-shell">{biometrics.fatigueScore.toFixed(2)}</dd></div>
          <div><dt>YAWNS/MIN</dt><dd className="text-shell">{biometrics.yawnsPerMin}</dd></div>
        </dl>
      )}

      {decision && decision.factors.length > 0 && (
        <ul className="mt-3 space-y-1 normal-case tracking-normal text-shell/80">
          {decision.factors.slice(0, 3).map((f) => <li key={f.signal}>· {f.message}</li>)}
        </ul>
      )}

      {advice && (
        <p className="mt-3 border-t border-pulse/20 pt-3 normal-case tracking-normal text-shell">
          “{advice.say}”
          <span className="ml-2 text-[9px] uppercase tracking-[0.2em] text-orbit">{advice.source === "llm" ? "GEMMA 4" : "RULES"}</span>
        </p>
      )}

      {error && <p className="mt-2 text-red-400">{error}</p>}
      <p className="mt-3 text-[9px] text-shell/40">CAMERA MEASURED · SLEEP, MOOD, CABIN: NOMINAL UNTIL G3/G6</p>
    </section>
  );
}
