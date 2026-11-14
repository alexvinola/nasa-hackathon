"use client";

import { useHotkey } from "@/modules/hud/useHotkey";
import type { SimMode } from "./useSimVitals";

const BUTTON = "border px-2 py-1";
const OFF = "border-shell/40 text-shell/80";

/**
 * Hand controls for the demo: raise a false warning or a false danger, loop the whole simulated shift, and mute the
 * alarm sounds. A false alarm is not drawn here: it changes the simulated readings, so it goes through the rules
 * engine like a real one. Pressing the button of an alarm that is already on switches it off; it never starts a
 * second one. Each label names the key that does the same.
 */
export function DebugPanel({
  mode,
  onMode,
  sound,
  onSound,
}: {
  mode: SimMode;
  onMode: (mode: SimMode) => void;
  sound: boolean;
  onSound: (on: boolean) => void;
}) {
  const toggle = (wanted: SimMode) => onMode(mode === wanted ? "live" : wanted);
  useHotkey("1", () => toggle("rest"));
  useHotkey("2", () => toggle("danger"));
  useHotkey("3", () => toggle("loop"));
  useHotkey("4", () => onSound(!sound));

  return (
    <section data-hud-panel className="absolute bottom-44 left-8 w-64 border border-pulse/30 bg-space/70 p-3 text-xs tracking-[0.12em] text-shell/80 backdrop-blur">
      <h2 className="text-pulse">DEBUG · FALSE ALARMS</h2>
      <div className="mt-2 grid grid-cols-2 gap-2">
        <button type="button" aria-pressed={mode === "rest"} onClick={() => toggle("rest")} className={`${BUTTON} ${mode === "rest" ? "border-amber-400 bg-amber-400/20 text-amber-300" : OFF}`}>
          WARNING {mode === "rest" ? "ON" : "OFF"} (1)
        </button>
        <button type="button" aria-pressed={mode === "danger"} onClick={() => toggle("danger")} className={`${BUTTON} ${mode === "danger" ? "border-red-500 bg-red-600/30 text-red-200" : OFF}`}>
          DANGER {mode === "danger" ? "ON" : "OFF"} (2)
        </button>
        <button type="button" aria-pressed={mode === "loop"} onClick={() => toggle("loop")} className={`${BUTTON} ${mode === "loop" ? "border-pulse bg-pulse/20 text-pulse" : OFF}`}>
          LOOP {mode === "loop" ? "ON" : "OFF"} (3)
        </button>
        <button type="button" aria-pressed={sound} onClick={() => onSound(!sound)} className={`${BUTTON} ${sound ? "border-pulse bg-pulse/20 text-pulse" : OFF}`}>
          SOUND {sound ? "ON" : "OFF"} (4)
        </button>
      </div>
    </section>
  );
}
