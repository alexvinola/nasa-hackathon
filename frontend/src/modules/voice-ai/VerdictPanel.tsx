"use client";

import { useState } from "react";
import { useT } from "@/i18n";
import type { Biometrics } from "@/modules/vision-hud/faceWorker";
import type { Decision, Status } from "./verdictApi";

const LIGHT: Record<Status, string> = {
  GREEN: "bg-emerald-400 shadow-[0_0_12px] shadow-emerald-400",
  AMBER: "bg-amber-400 shadow-[0_0_12px] shadow-amber-400",
  RED: "bg-red-500 shadow-[0_0_12px] shadow-red-500 animate-pulse",
};
const ESCALATION = { SELF_CARE: "voice.verdict.selfCare", CREW: "voice.verdict.crew", FLIGHT_SURGEON: "voice.verdict.surgeon" } as const;

/** One number of the drowsiness block: green while within its limit, amber past it. */
function Figure({ label, shown, over, tone }: { label: string; shown: string; over: boolean; tone?: string }) {
  return (
    <div>
      <div className="text-[11px] text-shell/80">{label}</div>
      <div className={`text-3xl leading-tight tracking-normal ${over ? "text-amber-300" : (tone ?? "text-emerald-300")}`}>{shown}</div>
    </div>
  );
}

/** A small reading with its bar against the engine's limit: amber when it reaches it. */
function Mini({ label, label2, value, unit, limit }: { label: string; label2: string; value: number; unit: string; limit?: number | null }) {
  const t = useT();
  const over = limit != null && value >= limit;
  return (
    <div>
      <span className="block">{label}</span>
      <span className={`block text-base leading-tight tracking-normal ${over ? "text-amber-300" : "text-shell"}`}>
        {value.toFixed(1)}
        <span className="ml-1 text-[11px] text-shell/70">{unit}</span>
      </span>
      {limit != null && (
        <>
          <div className="mt-1 h-1.5 overflow-hidden rounded bg-shell/15" role="meter" aria-label={label2} aria-valuemin={0} aria-valuemax={limit} aria-valuenow={Math.min(value, limit)}>
            <div className={`h-full ${over ? "bg-amber-400" : "bg-pulse"}`} style={{ width: `${Math.min(100, (value / limit) * 100)}%` }} />
          </div>
          <span className="mt-0.5 block text-[11px] text-shell/70">{t("voice.verdict.limit", { value: limit.toFixed(1), unit: "" })}</span>
        </>
      )}
    </div>
  );
}

/**
 * The rules engine's verdict over the HUD: traffic light, escalation, the readings and why. What PULSAR says about
 * it is the mascot's line, not repeated here. `simulated` marks readings that come from sim-core, not the camera.
 */
export function VerdictPanel({
  biometrics,
  decision,
  error,
  simulated,
  cabinCo2,
  cabinCo2Limit,
  radiation,
  radiationLimit,
  perclosLimit,
  fatigueLimit,
  onOpenGuide,
}: {
  biometrics: Biometrics | null;
  decision: Decision | null;
  error: string | null;
  simulated: boolean;
  /** Cabin CO2 in mmHg and the engine's limit for it; the gauge is hidden without a reading. */
  cabinCo2?: number;
  cabinCo2Limit?: number | null;
  /** Radiation dose in mSv and the engine's limit for it. */
  radiation?: number;
  radiationLimit?: number | null;
  /** The engine's limits for the share of time the eyes are closed (0 to 1) and for the fatigue score. */
  perclosLimit?: number | null;
  fatigueLimit?: number | null;
  /** Opens the indicator guide (G9) for a reading, by its contract signal. */
  onOpenGuide?: (signal: string) => void;
}) {
  const t = useT();
  const bpm = biometrics?.heartRateBpm;
  // Folds down to the traffic light and the escalation, which stay in view.
  const [open, setOpen] = useState(true);

  return (
    <section data-hud-panel className="hud-glass border pointer-events-auto absolute right-8 top-28 max-h-[calc(100vh-15.5rem)] w-80 overflow-y-auto [scrollbar-color:var(--color-pulse)_transparent] [scrollbar-width:thin] p-4 text-sm tracking-[0.1em] text-shell/80 backdrop-blur">
      <button type="button" aria-expanded={open} onClick={() => setOpen((was) => !was)} className="pointer-events-auto flex w-full items-center gap-3 text-left">
        <span className={`h-3 w-3 rounded-full ${decision ? LIGHT[decision.status] : "bg-orbit/40"}`} />
        <span className="text-pulse">{decision ? decision.status : t("voice.verdict.waiting")}</span>
        {decision && <span className="ml-auto text-orbit">{t(ESCALATION[decision.escalation])}</span>}
        <span aria-hidden className={`${decision ? "" : "ml-auto"} border border-pulse/40 px-1.5 text-xs leading-tight text-pulse`}>{open ? "−" : "+"}</span>
      </button>

      <div hidden={!open}>
      {biometrics && (
        // The drowsiness block is the centre of the panel: three numbers that turn amber past the limit the rules engine
        // applies (the engine has no rule for yawns, so that one only changes colour when there is any).
        <div data-fatigue-block className="mt-3 grid grid-cols-3 gap-2 rounded border border-pulse/40 bg-pulse/5 p-3 text-center">
          <Figure label={t("voice.verdict.fatigue")} shown={biometrics.fatigueScore.toFixed(2)} over={fatigueLimit != null && biometrics.fatigueScore >= fatigueLimit} />
          <Figure label="PERCLOS" shown={`${Math.round(biometrics.perclos * 100)}%`} over={perclosLimit != null && biometrics.perclos >= perclosLimit} />
          <Figure label={t("voice.verdict.yawns")} shown={String(biometrics.yawnsPerMin)} over={false} tone={biometrics.yawnsPerMin > 0 ? "text-orbit" : undefined} />
        </div>
      )}

      {(bpm != null || cabinCo2 != null || radiation != null) && (
        // One row for the secondary readings: heart rate, cabin CO2 and radiation, each with the engine's limit where it has one.
        <div data-secondary-readings className="mt-3 grid grid-cols-3 gap-2 text-xs text-shell/90">
          {bpm != null && (
            <button type="button" data-reading="biometrics.heartRateBpm" title={t("voice.verdict.pulseGuide")} onClick={() => onOpenGuide?.("biometrics.heartRateBpm")} className="pointer-events-auto text-left hover:text-pulse">
              <span className="block">{t("voice.verdict.pulseShort")}</span>
              <span className="block text-base leading-tight tracking-normal text-shell">
                <span aria-hidden className="hud-beat mr-1 inline-block text-red-400" style={{ animationDuration: `${60 / bpm}s` }}>♥</span>
                {bpm}
                <span className="ml-1 text-[11px] text-shell/70">{t("voice.verdict.bpmUnit")}</span>
              </span>
              <span className="mt-1 block text-[11px] text-red-300">{t("voice.verdict.simShort")}</span>
            </button>
          )}
          {cabinCo2 != null && <Mini label="CO2" value={cabinCo2} unit="mmHg" limit={cabinCo2Limit} label2={t("voice.verdict.co2Label")} />}
          {radiation != null && <Mini label={t("voice.verdict.radiationShort")} value={radiation} unit="mSv" limit={radiationLimit} label2={t("voice.verdict.radiationLabel")} />}
        </div>
      )}

      {decision && decision.factors.length > 0 && (
        <ul className="mt-3 space-y-1 text-base normal-case leading-snug tracking-normal text-shell">
          {decision.factors.slice(0, 3).map((f) => <li key={f.signal}>· {f.message}</li>)}
        </ul>
      )}

      {error && <p className="mt-2 text-red-400">{error}</p>}
      <p className="mt-3 text-[11px] text-shell/80">
        {simulated ? t("voice.verdict.simulated") : t("voice.verdict.measured")} · {t("voice.verdict.pending")}
      </p>
      </div>
    </section>
  );
}
