"use client";

import type { AlarmLevel } from "./useAlarmSound";
import { useHotkey } from "./useHotkey";

const LOOK = {
  clear: { box: "border-pulse text-pulse", label: "ALL CLEAR" },
  rest: { box: "border-amber-400 text-amber-300", label: "TIME TO REST" },
  danger: { box: "border-red-500 text-red-200", label: "DANGER" },
} as const;

function Icon({ level }: { level: AlarmLevel }) {
  const common = { viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", strokeWidth: 2, strokeLinecap: "round", strokeLinejoin: "round", "aria-hidden": true } as const;
  if (level === "danger") {
    return (
      <svg {...common} className="hud-beat h-8 w-8 shrink-0" style={{ animationDuration: "0.9s" }}>
        <path d="M12 3 2 20h20L12 3Z" />
        <path d="M12 10v5M12 18h.01" />
      </svg>
    );
  }
  if (level === "rest") {
    return (
      <svg {...common} className="h-6 w-6 shrink-0">
        <path d="M20 14.5A8 8 0 1 1 9.5 4a6.5 6.5 0 0 0 10.5 10.5Z" />
      </svg>
    );
  }
  return (
    <svg {...common} className="h-4 w-4 shrink-0">
      <path d="m5 12 5 5 9-10" />
    </svg>
  );
}

/**
 * The alert indicator at the top of the HUD: an icon and a label for the current alarm level and, during an alarm,
 * the steps of the countermeasure the rules engine chose. The astronaut stops the sound and the pulsing frame by
 * acknowledging it; the indicator itself only clears when the readings do.
 */
export function AlertIndicator({
  level,
  detail,
  steps,
  acknowledged,
  onAcknowledge,
}: {
  level: AlarmLevel;
  /** Appended to the label, e.g. "NOT SAFE TO STAY AWAKE". */
  detail?: string;
  steps: string[];
  acknowledged: boolean;
  onAcknowledge: () => void;
}) {
  const look = LOOK[level ?? "clear"];
  useHotkey("escape", () => level && !acknowledged && onAcknowledge());
  return (
    <section
      data-hud-panel
      role={level ? "alert" : "status"}
      // Centred in the width left of the verdict panel (20rem wide plus its 2rem margin), so the two never overlap.
      className={`absolute left-[calc((100vw-22rem)/2)] top-6 -translate-x-1/2 border-2 bg-space/95 px-4 py-3 text-sm tracking-[0.15em] backdrop-blur ${look.box} ${level ? "w-[min(32rem,calc(100vw-26rem))]" : ""}`}
    >
      <header className={`flex items-center justify-center gap-3 ${level === "danger" ? "text-lg font-bold" : level ? "text-base font-bold" : ""}`}>
        <Icon level={level} />
        <span>{look.label}{detail ? ` · ${detail}` : ""}</span>
      </header>
      {level && steps.length > 0 && (
        <>
          <p className="mt-3 text-center text-xs text-shell/90">DO THIS NOW</p>
          <ol className="mt-1 list-inside list-decimal space-y-2 text-center text-lg normal-case leading-snug tracking-normal text-white">
            {steps.map((step) => <li key={step}>{step}</li>)}
          </ol>
        </>
      )}
      {level && (
        <button
          type="button"
          disabled={acknowledged}
          onClick={onAcknowledge}
          className={`mt-3 w-full border-2 px-3 py-2 text-sm text-white disabled:opacity-60 ${level === "danger" ? "border-red-400 bg-red-600 font-bold" : "border-amber-300 bg-amber-400 font-bold !text-space"}`}
        >
          {acknowledged ? "UNDERSTOOD · ALARM STOPPED" : "I UNDERSTAND · STOP THE ALARM (ESC)"}
        </button>
      )}
    </section>
  );
}
