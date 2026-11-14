"use client";

import { create } from "zustand";
import type { Biometrics } from "@/modules/vision-hud/faceWorker";
import { evaluate, telemetryFrom, type Decision, type Telemetry } from "@/modules/voice-ai/verdictApi";
import { fetchRulebook, type Rulebook } from "./rulebook";

type TelemetryState = {
  /** The contract as last sent to the rules engine; null until a reading arrives. */
  telemetry: Telemetry | null;
  /** The engine's answer for it; null while it has not answered or is down. */
  decision: Decision | null;
  /** The engine's rules and countermeasures; null until it has listed them. */
  rulebook: Rulebook | null;
  /** True while the self-report block is still shared/examples/nominal.json, not something the astronaut reported. */
  selfReportIsExample: boolean;
  /** A whole contract in (judge sliders, a scenario): the engine is asked about it. */
  setTelemetry: (telemetry: Telemetry) => void;
  /** A camera reading in: the rest of the contract stays as it was, or starts from the nominal example. */
  setBiometrics: (biometrics: Biometrics) => void;
  loadRulebook: () => void;
};

let asked = 0;
let loading = false;

export const useTelemetry = create<TelemetryState>()((set, get) => {
  // A stale answer never overwrites a newer one. Engine down: the readings stay, the status is unknown.
  const send = (telemetry: Telemetry) => {
    const mine = ++asked;
    set({ telemetry });
    get().loadRulebook();
    evaluate(telemetry)
      .then((decision) => mine === asked && set({ decision }))
      .catch(() => mine === asked && set({ decision: null }));
  };

  return {
    telemetry: null,
    decision: null,
    rulebook: null,
    selfReportIsExample: false,
    setTelemetry: (telemetry) => {
      // A different contract: the last verdict was not about it. (Camera readings keep theirs; a new one is under 2 s away.)
      set({ selfReportIsExample: false, decision: null });
      send(telemetry);
    },
    setBiometrics: (biometrics) => {
      const current = get().telemetry;
      if (!current) set({ selfReportIsExample: true });
      send(current ? ({ ...current, timestamp: Math.floor(Date.now() / 1000), biometrics } as Telemetry) : telemetryFrom(biometrics));
    },
    loadRulebook: () => {
      if (get().rulebook || loading) return;
      loading = true;
      fetchRulebook()
        .then((rulebook) => set({ rulebook }))
        .catch(() => undefined) // backend down: the twin asks again
        .finally(() => (loading = false));
    },
  };
});

// Test mode only (a browser driven by automation): the acceptance checks load a scenario and read the state here.
if (typeof navigator !== "undefined" && navigator.webdriver) {
  (window as unknown as { __synapse?: typeof useTelemetry }).__synapse = useTelemetry;
}
