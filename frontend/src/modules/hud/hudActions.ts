"use client";

import { useEffect, useRef } from "react";

/**
 * What PULSAR can ask the HUD to do when the astronaut talks or types to it ("open relaxation", "log 30 minutes of
 * exercise", "how do I measure my blood pressure"). The backend matches the request against a closed list
 * (backend/pulsar/hud_actions.py) and sends one of these; the model never writes one. Every panel that owns a piece of
 * the HUD listens for the actions that concern it and checks them again before doing anything.
 */
export type HudAction =
  | { type: "open_relax"; exercise: "breathe" | "eyes" | "body" | null }
  | { type: "open_measure"; signal: string | null }
  | { type: "set_measure"; signal: string; values: Record<string, number> }
  | { type: "log_habit"; habit: string; amount: number }
  | { type: "open_habits"; expand: boolean }
  | { type: "open_health"; id: string | null }
  | { type: "close_panels" }
  | { type: "set_language"; lang: "es" | "en" }
  | { type: "dev_menu"; open: boolean }
  | { type: "set_overlay"; target: "mesh" | "ai_check"; on: boolean };

const EVENT = "pulsar:hud-action";

export function dispatchHudAction(action: HudAction) {
  window.dispatchEvent(new CustomEvent<HudAction>(EVENT, { detail: action }));
}

/** Runs `handler` for every action PULSAR sends to the HUD, for as long as the component is mounted. */
export function useHudAction(handler: (action: HudAction) => void) {
  const latest = useRef(handler);
  latest.current = handler;
  useEffect(() => {
    const on = (event: Event) => latest.current((event as CustomEvent<HudAction>).detail);
    window.addEventListener(EVENT, on);
    return () => window.removeEventListener(EVENT, on);
  }, []);
}
