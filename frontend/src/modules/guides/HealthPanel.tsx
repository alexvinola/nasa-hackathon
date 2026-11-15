"use client";

import { useState } from "react";
import hrp from "../../../../shared/hrp.json";
import { HealthAnimation } from "./HealthAnimation";
import { useLang, useT } from "@/i18n";
import { healthText, type HealthPoint } from "./healthPoints";

/**
 * One body point of the SALUD tab: the 3D picture, the official HRP risks it covers, the problems and tools the
 * NASA pages name, and what to do, to yourself or to a crewmate. PULSAR does not measure or judge any of it.
 */
export function HealthPanel({ point, onClose }: { point: HealthPoint; onClose: () => void }) {
  const t = useT();
  const lang = useLang();
  const [withMate, setWithMate] = useState(false);
  const [active, setActive] = useState(-1); // the step the animation is on; -1 while it shows the whole body
  const steps = healthText(withMate ? point.mate : point.self, lang);
  const label = healthText(point.label, lang);
  const TAB = "border px-3 py-1 text-xs tracking-[0.12em]";
  return (
    <section
      data-hud-panel
      data-health={point.id}
      aria-label={t("guides.health.aria", { label })}
      className="fixed inset-2 z-20 flex flex-col overflow-hidden border-2 border-pulse/60 bg-space/90 text-sm text-shell backdrop-blur md:absolute md:inset-auto md:left-[19rem] md:top-24 md:z-10 md:max-h-[calc(100vh-17rem)] md:w-[40rem] md:max-w-[calc(100vw-43rem)] md:bg-space/70"
    >
      <header className="flex items-start gap-3 shrink-0 border-b border-pulse/30 px-4 py-3">
        <div>
          <h2 className="text-lg tracking-[0.15em] text-pulse">{label.toUpperCase()}</h2>
          <p className="text-xs tracking-[0.1em] text-shell/70">{point.risks.map((id) => hrp.risks[id].name).join(" · ")}</p>
        </div>
        <button type="button" onClick={onClose} aria-label={t("guides.health.closeAria")} className="ml-auto border border-shell/40 px-2 py-1 text-xs tracking-[0.15em] text-shell/80 hover:border-shell">
          {t("guides.panel.close")}
        </button>
      </header>
      <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain p-4">

      <div role="tablist" aria-label={t("guides.health.tabsAria")} className="mt-3 flex gap-2">
        <button type="button" role="tab" aria-selected={!withMate} onClick={() => setWithMate(false)} className={`${TAB} ${!withMate ? "border-pulse bg-pulse/20 text-pulse" : "border-shell/40 text-shell/80"}`}>
          {t("guides.health.tabSelf")}
        </button>
        <button type="button" role="tab" aria-selected={withMate} onClick={() => setWithMate(true)} className={`${TAB} ${withMate ? "border-pulse bg-pulse/20 text-pulse" : "border-shell/40 text-shell/80"}`}>
          {t("guides.health.tabMate")}
        </button>
      </div>

      <div className="mt-3 flex gap-4">
        <HealthAnimation point={point} withMate={withMate} label={label} steps={steps.length} onStep={setActive} />
        <div className="min-w-0 flex-1">
          <h3 className="text-xs tracking-[0.15em] text-orbit">{withMate ? t("guides.health.headMate") : t("guides.health.headSelf")}</h3>
          <ol className="mt-1 space-y-1 leading-snug">
            {steps.map((step, index) => (
              <li key={step} data-active={active === index} className={`flex gap-2 ${active === index ? "text-pulse" : ""}`}>
                <span className="text-pulse">{index + 1}.</span>
                <span>{step}</span>
              </li>
            ))}
          </ol>
        </div>
      </div>

      <h3 className="mt-3 text-xs tracking-[0.15em] text-orbit">{t("guides.health.problems")}</h3>
      <ul className="mt-1 list-inside list-disc leading-snug">
        {healthText(point.problems, lang).map((problem) => <li key={problem}>{problem}</li>)}
      </ul>

      <h3 className="mt-3 text-xs tracking-[0.15em] text-orbit">{t("guides.health.tools")}</h3>
      <p className="mt-1 leading-snug">{healthText(point.tools, lang)}</p>

      <p className="mt-3 border-t border-pulse/20 pt-2 text-[11px] tracking-[0.1em] text-shell/60">
        {t("guides.health.sources")}{" "}
        {point.pages.map((page, index) => (
          <span key={page}>
            {index > 0 && " · "}
            {page.replace("https://www.nasa.gov/", "nasa.gov/")}
          </span>
        ))}{" "}
        {t("guides.health.note")} <span className="text-orbit">{t("guides.health.notDevice")}</span>
      </p>
      </div>
    </section>
  );
}
