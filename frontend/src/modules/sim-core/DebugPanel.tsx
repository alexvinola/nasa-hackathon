"use client";

import { useHotkey } from "@/modules/hud/useHotkey";
import type { SimMode } from "./useSimVitals";

const NOW: Record<SimMode, string> = {
  live: "Real readings. No test running.",
  rest: "Testing the amber warning (tired).",
  danger: "Testing the red danger (exhausted).",
  loop: "Demo: a whole shift on repeat, from rested to exhausted and back.",
};

function Switch({ on, tone, hotkey, title, hint, onClick }: { on: boolean; tone: string; hotkey: string; title: string; hint: string; onClick: () => void }) {
  return (
    <button type="button" aria-pressed={on} onClick={onClick} className={`flex w-full items-center gap-2 border-2 px-2 py-1 text-left ${on ? tone : "border-shell/60 text-shell"}`}>
      <span className="w-9 shrink-0 text-center font-bold">{on ? "ON" : "OFF"}</span>
      <span className="min-w-0 flex-1">
        <span className="block font-bold">{title}</span>
        <span className="block normal-case tracking-normal opacity-90">{hint}</span>
      </span>
      <kbd className="shrink-0 border border-current px-1">{hotkey}</kbd>
    </button>
  );
}

/**
 * Hand controls for the demo: raise a false warning or a false danger, loop the whole simulated shift, and mute the
 * alarm sounds. A false alarm is not drawn here: it changes the simulated readings, so it goes through the rules
 * engine like a real one. Pressing the switch of an alarm that is already on switches it off; it never starts a
 * second one. Each switch shows the key that does the same.
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
    <section data-hud-panel className="absolute bottom-44 left-8 w-72 border-2 border-pulse/60 bg-space/90 p-3 text-xs tracking-[0.1em] text-shell backdrop-blur">
      <h2 className="font-bold text-pulse">TEST PANEL · NOT REAL DATA</h2>
      <p className="mt-1 normal-case tracking-normal text-shell/90">Pretend the astronaut is tired to see how PULSAR reacts.</p>
      <div className="mt-2 space-y-1">
        <Switch on={mode === "rest"} tone="border-amber-400 bg-amber-400 text-space" hotkey="1" title="FAKE WARNING" hint="Tired: amber alarm" onClick={() => toggle("rest")} />
        <Switch on={mode === "danger"} tone="border-red-500 bg-red-600 text-white" hotkey="2" title="FAKE DANGER" hint="Exhausted: red alarm" onClick={() => toggle("danger")} />
        <Switch on={mode === "loop"} tone="border-pulse bg-pulse text-space" hotkey="3" title="AUTO DEMO" hint="Plays a whole shift on repeat" onClick={() => toggle("loop")} />
        <Switch on={sound} tone="border-pulse bg-pulse text-space" hotkey="4" title="ALARM SOUND" hint="Mute or unmute the alarms" onClick={() => onSound(!sound)} />
      </div>
      <p role="status" className="mt-2 normal-case tracking-normal text-shell/90">Now: {NOW[mode]}</p>
    </section>
  );
}
