"use client";

import { useState } from "react";
import type { Biometrics } from "@/modules/vision-hud/faceWorker";
import type { Advice, Decision, Status } from "./verdictApi";

const LIGHT: Record<Status, string> = {
  GREEN: "bg-emerald-400 shadow-[0_0_12px] shadow-emerald-400",
  AMBER: "bg-amber-400 shadow-[0_0_12px] shadow-amber-400",
  RED: "bg-red-500 shadow-[0_0_12px] shadow-red-500 animate-pulse",
};
const ESCALATION = { SELF_CARE: "AUTOCUIDADO", CREW: "AVISA A LA TRIPULACIÓN", FLIGHT_SURGEON: "CIRUJANO DE VUELO" } as const;

/**
 * The rules engine's verdict over the HUD: traffic light, escalation, the readings and why. What PULSAR says about
 * it is the mascot's line, not repeated here. `simulated` marks readings that come from sim-core, not the camera.
 */
export function VerdictPanel({
  biometrics,
  decision,
  advice,
  error,
  simulated,
  cabinCo2,
  cabinCo2Limit,
  radiation,
  radiationLimit,
  onOpenGuide,
}: {
  biometrics: Biometrics | null;
  decision: Decision | null;
  advice: Advice | null;
  error: string | null;
  simulated: boolean;
  /** Cabin CO2 in mmHg and the engine's limit for it; the gauge is hidden without a reading. */
  cabinCo2?: number;
  cabinCo2Limit?: number | null;
  /** Radiation dose in mSv and the engine's limit for it. */
  radiation?: number;
  radiationLimit?: number | null;
  /** Opens the indicator guide (G9) for a reading, by its contract signal. */
  onOpenGuide?: (signal: string) => void;
}) {
  const bpm = biometrics?.heartRateBpm;
  // Folds down to the traffic light and the escalation, which stay in view.
  const [open, setOpen] = useState(true);

  return (
    <section data-hud-panel className="pointer-events-none absolute right-8 top-20 w-80 rounded-lg border border-pulse/30 bg-space/60 p-4 text-sm tracking-[0.1em] text-shell/80 backdrop-blur">
      <button type="button" aria-expanded={open} onClick={() => setOpen((was) => !was)} className="pointer-events-auto flex w-full items-center gap-3 text-left">
        <span className={`h-3 w-3 rounded-full ${decision ? LIGHT[decision.status] : "bg-orbit/40"}`} />
        <span className="text-pulse">{decision ? decision.status : "ESPERANDO LECTURAS"}</span>
        {decision && <span className="ml-auto text-orbit">{ESCALATION[decision.escalation]}</span>}
        <span aria-hidden className={`${decision ? "" : "ml-auto"} border border-pulse/40 px-1.5 text-xs leading-tight text-pulse`}>{open ? "−" : "+"}</span>
      </button>

      <div hidden={!open}>
      {bpm != null && (
        // Everything here keeps time with the heart: one beat of the icon and one sweep of the trace per heartbeat.
        <button
          type="button"
          data-reading="biometrics.heartRateBpm"
          title="Cómo tomarte el pulso"
          onClick={() => onOpenGuide?.("biometrics.heartRateBpm")}
          className="pointer-events-auto mt-3 flex w-full items-center gap-3 rounded border border-red-400/40 bg-red-500/10 px-3 py-2 text-left tracking-[0.1em] hover:border-red-300"
        >
          <span aria-hidden className="hud-beat text-3xl leading-none text-red-400" style={{ animationDuration: `${60 / bpm}s` }}>♥</span>
          <span>
            <span className="block text-2xl leading-none tracking-normal text-shell">{bpm}<span className="ml-1 text-xs text-shell/70">LPM</span></span>
            <span className="mt-1 block text-xs text-red-300">PULSO · SIMULADO</span>
          </span>
          <svg aria-hidden viewBox="0 0 120 32" className="ml-auto h-8 w-28 text-red-400">
            <polyline
              className="hud-ecg"
              style={{ animationDuration: `${60 / bpm}s` }}
              points="0,18 26,18 32,12 38,18 46,18 50,26 56,3 62,29 67,18 78,18 86,11 95,18 120,18"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinejoin="round"
              pathLength={100}
            />
          </svg>
        </button>
      )}

      {biometrics && (
        <dl className="mt-3 grid grid-cols-3 gap-2 text-xs text-shell/90">
          <div><dt>PERCLOS</dt><dd className="text-base text-shell">{Math.round(biometrics.perclos * 100)}%</dd></div>
          <div><dt>FATIGA</dt><dd className="text-base text-shell">{biometrics.fatigueScore.toFixed(2)}</dd></div>
          <div><dt>BOSTEZOS/MIN</dt><dd className="text-base text-shell">{biometrics.yawnsPerMin}</dd></div>
        </dl>
      )}

      {cabinCo2 != null && (
        // Cabin air: the CO2 reading against the limit the rules engine applies to it.
        <div className="mt-3">
          <div className="flex justify-between text-xs text-shell/90">
            <span>CO2 DE LA CABINA · SIMULADO</span>
            <span className="text-base text-shell">{cabinCo2.toFixed(1)}<span className="ml-1 text-xs text-shell/90">mmHg</span></span>
          </div>
          {cabinCo2Limit != null && (
            <>
              <div className="mt-1 h-2 overflow-hidden rounded bg-shell/15" role="meter" aria-label="CO2 de la cabina" aria-valuemin={0} aria-valuemax={cabinCo2Limit} aria-valuenow={cabinCo2}>
                <div
                  className={`h-full ${cabinCo2 > cabinCo2Limit ? "bg-amber-400" : "bg-pulse"}`}
                  style={{ width: `${Math.min(100, (cabinCo2 / cabinCo2Limit) * 100)}%` }}
                />
              </div>
              <div className="mt-1 text-right text-[11px] text-shell/80">LÍMITE {cabinCo2Limit.toFixed(1)} mmHg</div>
            </>
          )}
        </div>
      )}

      {radiation != null && (
        <div className="mt-3">
          <div className="flex justify-between text-xs text-shell/90">
            <span>RADIACIÓN · SIMULADA</span>
            <span className="text-base text-shell">{radiation.toFixed(1)}<span className="ml-1 text-xs text-shell/90">mSv</span></span>
          </div>
          {radiationLimit != null && (
            <>
              <div className="mt-1 h-2 overflow-hidden rounded bg-shell/15" role="meter" aria-label="Dosis de radiación" aria-valuemin={0} aria-valuemax={radiationLimit} aria-valuenow={radiation}>
                <div
                  className={`h-full ${radiation >= radiationLimit ? "bg-amber-400" : "bg-pulse"}`}
                  style={{ width: `${Math.min(100, (radiation / radiationLimit) * 100)}%` }}
                />
              </div>
              <div className="mt-1 text-right text-[11px] text-shell/80">LÍMITE {radiationLimit.toFixed(1)} mSv</div>
            </>
          )}
        </div>
      )}

      {decision && decision.factors.length > 0 && (
        <ul className="mt-3 space-y-1 text-base normal-case leading-snug tracking-normal text-shell">
          {decision.factors.slice(0, 3).map((f) => <li key={f.signal}>· {f.message}</li>)}
        </ul>
      )}

      {advice && (
        <p className="mt-3 border-t border-pulse/20 pt-3 text-xs uppercase tracking-[0.15em] text-orbit">
          PULSAR LO DICE · {advice.source === "llm" ? "GEMMA 4" : "REGLAS"}
        </p>
      )}

      {error && <p className="mt-2 text-red-400">{error}</p>}
      <p className="mt-3 text-[11px] text-shell/80">
        {simulated ? "LECTURAS SIMULADAS · SIN CÁMARA" : "MEDIDO POR CÁMARA · PULSO SIMULADO"} · SUEÑO, ÁNIMO, CABINA: NOMINAL HASTA G3/G6
      </p>
      </div>
    </section>
  );
}
