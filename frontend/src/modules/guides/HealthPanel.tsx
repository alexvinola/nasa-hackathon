"use client";

import { useState } from "react";
import hrp from "../../../../shared/hrp.json";
import { HealthAnimation } from "./HealthAnimation";
import type { HealthPoint } from "./healthPoints";

/**
 * One body point of the SALUD tab: the 3D picture, the official HRP risks it covers, the problems and tools the
 * NASA pages name, and what to do, to yourself or to a crewmate. PULSAR does not measure or judge any of it.
 */
export function HealthPanel({ point, onClose }: { point: HealthPoint; onClose: () => void }) {
  const [withMate, setWithMate] = useState(false);
  const steps = withMate ? point.mate : point.self;
  const TAB = "border px-3 py-1 text-xs tracking-[0.12em]";
  return (
    <section
      data-hud-panel
      data-health={point.id}
      aria-label={`Salud: ${point.label}`}
      className="absolute left-[19rem] top-24 z-10 max-h-[calc(100vh-17rem)] w-[40rem] max-w-[calc(100vw-43rem)] overflow-y-auto border-2 border-pulse/60 bg-space/70 p-4 text-sm text-shell backdrop-blur"
    >
      <header className="flex items-start gap-3">
        <div>
          <h2 className="text-lg tracking-[0.15em] text-pulse">{point.label.toUpperCase()}</h2>
          <p className="text-xs tracking-[0.1em] text-shell/70">{point.risks.map((id) => hrp.risks[id].name).join(" · ")}</p>
        </div>
        <button type="button" onClick={onClose} aria-label="Cerrar la guía de salud" className="ml-auto border border-shell/40 px-2 py-1 text-xs tracking-[0.15em] text-shell/80 hover:border-shell">
          CERRAR ✕
        </button>
      </header>

      <div role="tablist" aria-label="A quién ayudas" className="mt-3 flex gap-2">
        <button type="button" role="tab" aria-selected={!withMate} onClick={() => setWithMate(false)} className={`${TAB} ${!withMate ? "border-pulse bg-pulse/20 text-pulse" : "border-shell/40 text-shell/80"}`}>
          A TI
        </button>
        <button type="button" role="tab" aria-selected={withMate} onClick={() => setWithMate(true)} className={`${TAB} ${withMate ? "border-pulse bg-pulse/20 text-pulse" : "border-shell/40 text-shell/80"}`}>
          A UN COMPAÑERO
        </button>
      </div>

      <div className="mt-3 flex gap-4">
        <HealthAnimation point={point} withMate={withMate} label={point.label} />
        <div className="min-w-0 flex-1">
          <h3 className="text-xs tracking-[0.15em] text-orbit">{withMate ? "SI LE PASA A UN COMPAÑERO" : "SI TE PASA A TI"}</h3>
          <ol className="mt-1 space-y-1 leading-snug">
            {steps.map((step, index) => (
              <li key={step} className="flex gap-2">
                <span className="text-pulse">{index + 1}.</span>
                <span>{step}</span>
              </li>
            ))}
          </ol>
        </div>
      </div>

      <h3 className="mt-3 text-xs tracking-[0.15em] text-orbit">PROBLEMAS POSIBLES</h3>
      <ul className="mt-1 list-inside list-disc leading-snug">
        {point.problems.map((problem) => <li key={problem}>{problem}</li>)}
      </ul>

      <h3 className="mt-3 text-xs tracking-[0.15em] text-orbit">HERRAMIENTAS QUE NOMBRA LA NASA</h3>
      <p className="mt-1 leading-snug">{point.tools}</p>

      <p className="mt-3 border-t border-pulse/20 pt-2 text-[11px] tracking-[0.1em] text-shell/60">
        FUENTES: hrp-risks ·{" "}
        {point.pages.map((page, index) => (
          <span key={page}>
            {index > 0 && " · "}
            {page.replace("https://www.nasa.gov/", "nasa.gov/")}
          </span>
        ))}{" "}
        · PASOS: REDACCIÓN DEL EQUIPO, NO ES GUÍA CLÍNICA · <span className="text-orbit">NO ES UN DISPOSITIVO MÉDICO</span>
      </p>
    </section>
  );
}
