"use client";

import { HudPanel } from "@/modules/hud/HudPanel";
import { useHotkey } from "@/modules/hud/useHotkey";
import { useT } from "@/i18n";
import type { SimMode } from "./useSimVitals";

const BUTTON = "border px-2 py-1";
const OFF = "border-shell/40 text-shell/80";

/**
 * Hand controls for the demo: raise a false warning or a false danger, push the cabin CO2 or the radiation dose over their limit, loop the
 * whole simulated shift, and mute the alarm sounds. A false alarm is not drawn here: it changes the simulated readings, so it goes through the rules
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
  const t = useT();
  const st = (on: boolean) => t(on ? "debug.on" : "debug.off");
  const toggle = (wanted: SimMode) => onMode(mode === wanted ? "live" : wanted);
  useHotkey("1", () => toggle("rest"));
  useHotkey("2", () => toggle("danger"));
  useHotkey("3", () => toggle("loop"));
  useHotkey("4", () => onSound(!sound));
  useHotkey("5", () => toggle("co2"));
  useHotkey("6", () => toggle("radiation"));

  return (
    <HudPanel title={t("debug.title")} defaultOpen={false} up>
      <div className="grid grid-cols-2 gap-2">
        <button type="button" aria-pressed={mode === "rest"} onClick={() => toggle("rest")} className={`${BUTTON} ${mode === "rest" ? "border-amber-400 bg-amber-400/20 text-amber-300" : OFF}`}>
          {t("debug.warning", { state: st(mode === "rest") })}
        </button>
        <button type="button" aria-pressed={mode === "danger"} onClick={() => toggle("danger")} className={`${BUTTON} ${mode === "danger" ? "border-red-500 bg-red-600/30 text-red-200" : OFF}`}>
          {t("debug.danger", { state: st(mode === "danger") })}
        </button>
        <button type="button" aria-pressed={mode === "loop"} onClick={() => toggle("loop")} className={`${BUTTON} ${mode === "loop" ? "border-pulse bg-pulse/20 text-pulse" : OFF}`}>
          {t("debug.loop", { state: st(mode === "loop") })}
        </button>
        <button type="button" aria-pressed={sound} onClick={() => onSound(!sound)} className={`${BUTTON} ${sound ? "border-pulse bg-pulse/20 text-pulse" : OFF}`}>
          {t("debug.sound", { state: st(sound) })}
        </button>
        <button type="button" aria-pressed={mode === "co2"} onClick={() => toggle("co2")} className={`${BUTTON} ${mode === "co2" ? "border-amber-400 bg-amber-400/20 text-amber-300" : OFF}`}>
          {t("debug.co2", { state: st(mode === "co2") })}
        </button>
        <button type="button" aria-pressed={mode === "radiation"} onClick={() => toggle("radiation")} className={`${BUTTON} ${mode === "radiation" ? "border-amber-400 bg-amber-400/20 text-amber-300" : OFF}`}>
          {t("debug.radiation", { state: st(mode === "radiation") })}
        </button>
      </div>
    </HudPanel>
  );
}
