"use client";

import { useEffect, useState } from "react";
import { GuideAnimation } from "./GuideAnimation";
import { useLang, useT, type Key } from "@/i18n";
import { localizedGuide, type Guide, type GuideStatus } from "./guides";

const TONE: Record<GuideStatus, string> = {
  GREEN: "border-emerald-400 text-emerald-300",
  AMBER: "border-amber-400 text-amber-300",
  RED: "border-red-500 text-red-300",
  "NOT JUDGED": "border-orbit text-orbit",
  WAITING: "border-shell/40 text-shell/70",
};
const STEP_EVERY_MS = 4000;

/**
 * One indicator's guide: how to take the measurement (numbered steps beside a looping picture of it), why it
 * matters in spaceflight and what to do when it looks wrong. It shows the current value and the status the rules
 * engine gives it; it never judges the value itself and quotes no range.
 */
export function GuidePanel({ guide: original, value, status, onClose }: { guide: Guide; value: string; status: GuideStatus; onClose: () => void }) {
  const t = useT();
  const guide = localizedGuide(original, useLang());
  const [step, setStep] = useState(0);
  // The steps play in a loop with the picture until the astronaut picks one; never under reduced motion.
  const [auto, setAuto] = useState(true);
  useEffect(() => {
    if (!auto || matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const id = setInterval(() => setStep((current) => (current + 1) % guide.how.length), STEP_EVERY_MS);
    return () => clearInterval(id);
  }, [auto, guide.how.length]);

  return (
    <section
      data-hud-panel
      data-guide={guide.signal}
      aria-label={t("guides.panel.aria", { label: guide.label })}
      className="absolute left-[19rem] top-24 z-10 max-h-[calc(100vh-17rem)] w-[40rem] max-w-[calc(100vw-43rem)] overflow-y-auto border-2 border-pulse/60 bg-space/70 p-4 text-sm text-shell backdrop-blur"
    >
      <header className="flex items-start gap-3">
        <div>
          <h2 className="text-lg tracking-[0.15em] text-pulse">{guide.label.toUpperCase()}</h2>
          <p className="text-xs tracking-[0.1em] text-shell/70">{guide.instrument}</p>
        </div>
        <button type="button" onClick={onClose} aria-label={t("guides.panel.closeAria")} className="ml-auto border border-shell/40 px-2 py-1 text-xs tracking-[0.15em] text-shell/80 hover:border-shell">
          {t("guides.panel.close")}
        </button>
      </header>

      <div className="mt-3 flex gap-4">
        <div>
          <GuideAnimation signal={guide.signal} focus={guide.how[step].focus} label={guide.label} />
          <dl className="mt-2 w-64 text-xs tracking-[0.1em] text-shell/70">
            <dt>{t("guides.panel.now")}</dt>
            <dd data-guide-value className="text-xl tracking-normal text-shell">{value}</dd>
            <dt className="mt-1">{t("guides.panel.engine")}</dt>
            <dd data-guide-status className={`mt-1 inline-block border px-2 py-0.5 text-sm ${TONE[status]}`}>{t(`guides.verdict.${status}` as Key)}</dd>
          </dl>
        </div>

        <div className="min-w-0 flex-1">
          <h3 className="text-xs tracking-[0.15em] text-orbit">{t("guides.panel.how")}</h3>
          <ol className="mt-1 space-y-1">
            {guide.how.map((item, index) => (
              <li key={item.text}>
                <button
                  type="button"
                  data-guide-step
                  aria-current={index === step ? "step" : undefined}
                  onClick={() => {
                    setAuto(false);
                    setStep(index);
                  }}
                  className={`flex w-full gap-2 border px-2 py-1 text-left leading-snug ${index === step ? "border-pulse bg-pulse/15 text-shell" : "border-transparent text-shell/70 hover:border-shell/30"}`}
                >
                  <span className="text-pulse">{index + 1}.</span>
                  <span>{item.text}</span>
                </button>
              </li>
            ))}
          </ol>
        </div>
      </div>

      <h3 className="mt-3 text-xs tracking-[0.15em] text-orbit">{t("guides.panel.why")}</h3>
      <p className="mt-1 leading-snug">{guide.why}</p>

      <h3 className="mt-3 text-xs tracking-[0.15em] text-orbit">{t("guides.panel.abnormal")}</h3>
      <p className="mt-1 leading-snug">{guide.whenAbnormal.text}</p>
      {guide.whenAbnormal.countermeasureIds.length > 0 && (
        // Rule ids stay out of sight: some carry their limit in the name, and a guide quotes no threshold.
        <p className="mt-1 text-xs text-shell/60">{t("guides.panel.countermeasure", { ids: guide.whenAbnormal.countermeasureIds.join(", ") })}</p>
      )}

      <p className="mt-3 border-t border-pulse/20 pt-2 text-[11px] tracking-[0.1em] text-shell/60">
        {t("guides.panel.sources", { sources: guide.sources.join(", ") })}{guide.assumption ? t("guides.panel.teamSteps") : ""} · <span className="text-orbit">{t("guides.panel.notDevice")}</span>
      </p>
    </section>
  );
}
