"use client";

import { useEffect, useState } from "react";
import registry from "../../../../shared/sources.json";
import { NOTICE, STATUS_COLOR, STATUS_LABEL, type Guide, type IndicatorStatus } from "./indicators";
import type { Rulebook } from "./rulebook";

const SOURCES: Record<string, { title: string }> = registry.sources;

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="mt-4 border-t border-pulse/20 pt-3">
      <h3 className="text-[10px] tracking-[0.2em] text-pulse">{title}</h3>
      {children}
    </section>
  );
}

/**
 * One indicator's guide, read as a manual: how to take the measurement (one step at a time), why it matters in
 * spaceflight and what to do when it is out of range. It quotes no limits: the status is the engine's, and the
 * steps to follow are the engine's countermeasures.
 */
export function GuidePanel({
  guide,
  reading,
  status,
  example,
  rulebook,
  onClose,
}: {
  guide: Guide;
  /** The current value with its unit; null when there is no reading. */
  reading: string | null;
  status: IndicatorStatus;
  /** The value is the nominal example, not something the astronaut reported. */
  example: boolean;
  rulebook: Rulebook | null;
  onClose: () => void;
}) {
  // The step the astronaut is on; the ones before it are done.
  const [step, setStep] = useState(0);
  const last = guide.how.length - 1;

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => event.key === "Escape" && onClose();
    addEventListener("keydown", onKey);
    return () => removeEventListener("keydown", onKey);
  }, [onClose]);

  const { ruleIds, countermeasureIds, note } = guide.whenAbnormal;
  const flagged = status === "AMBER" || status === "RED";

  return (
    <aside
      data-testid="indicator-guide"
      data-signal={guide.signal}
      data-status={status}
      aria-label={`${guide.label}: measurement guide`}
      className="pointer-events-auto flex max-h-full min-h-0 w-[380px] flex-col rounded-lg border border-pulse/30 bg-space/85 text-[11px] text-shell/80 backdrop-blur"
    >
      <header className="flex items-start gap-3 p-4 pb-3">
        <div className="min-w-0 flex-1">
          <p className="text-[9px] tracking-[0.2em] text-orbit">MEASUREMENT GUIDE</p>
          <h2 className="mt-1 text-sm uppercase tracking-[0.12em] text-shell">{guide.label}</h2>
        </div>
        <button type="button" onClick={onClose} aria-label="Close the guide" className="border border-shell/30 px-2 py-0.5 text-shell/70 hover:border-pulse hover:text-pulse">
          ESC
        </button>
      </header>

      <div className="min-h-0 flex-1 overflow-y-auto px-4 pb-4">
        <div className="flex items-end justify-between gap-3">
          <div>
            <p className="text-[9px] tracking-[0.2em] text-shell/50">CURRENT VALUE</p>
            <p data-testid="guide-value" className="text-lg text-shell">
              {reading ?? "NO READING"}
              {reading && example && <span className="ml-2 text-[9px] tracking-[0.2em] text-orbit">EXAMPLE DATA</span>}
            </p>
          </div>
          <p className="flex items-center gap-2 pb-1 text-[10px] tracking-[0.15em]" style={{ color: STATUS_COLOR[status] }}>
            <span className={`h-2.5 w-2.5 rounded-full ${status === "RED" ? "animate-pulse" : ""}`} style={{ background: STATUS_COLOR[status] }} />
            {STATUS_LABEL[status]}
          </p>
        </div>

        <Section title="HOW TO MEASURE">
          <p className="mt-1 text-shell/60">{guide.method}</p>
          <ol data-testid="guide-how" className="mt-2 list-decimal space-y-1 pl-5">
            {guide.how.map((text, i) => (
              <li
                key={text}
                aria-current={i === step ? "step" : undefined}
                onClick={() => setStep(i)}
                className={`cursor-pointer rounded px-2 py-1.5 leading-snug ${i === step ? "bg-pulse/15 text-shell marker:text-pulse" : i < step ? "text-shell/40" : "text-shell/70"}`}
              >
                {text}
              </li>
            ))}
          </ol>
          <div className="mt-2 flex items-center gap-2 text-[10px] tracking-[0.15em]">
            <button type="button" disabled={step === 0} onClick={() => setStep(step - 1)} className="border border-shell/30 px-2 py-1 text-shell/70 disabled:opacity-30">
              BACK
            </button>
            <button type="button" onClick={() => setStep(step === last ? 0 : step + 1)} className="border border-pulse bg-pulse/20 px-2 py-1 text-pulse">
              {step === last ? "START AGAIN" : "NEXT STEP"}
            </button>
            <span className="ml-auto text-shell/50">STEP {step + 1} / {guide.how.length}</span>
          </div>
        </Section>

        <Section title="WHY IT MATTERS IN SPACEFLIGHT">
          <p className="mt-1 leading-relaxed">{guide.why}</p>
        </Section>

        <Section title="IF IT IS OUT OF RANGE">
          <p className="mt-1 leading-relaxed" style={flagged ? { color: STATUS_COLOR[status] } : undefined}>{note}</p>
          {countermeasureIds.map((id) => {
            const countermeasure = rulebook?.countermeasures.find((c) => c.id === id);
            return (
              <div key={id} className="mt-2">
                <p className="text-[10px] uppercase tracking-[0.12em] text-shell">
                  {countermeasure ? countermeasure.title : id} <span className="text-shell/40">· {id}</span>
                </p>
                {countermeasure ? (
                  <ol className="mt-1 list-decimal space-y-0.5 pl-5 leading-snug">
                    {countermeasure.steps.map((text) => <li key={text}>{text}</li>)}
                  </ol>
                ) : (
                  <p className="mt-1 text-shell/50">The rules engine is not answering, so its steps cannot be listed.</p>
                )}
              </div>
            );
          })}
          {ruleIds.length > 0 && <p className="mt-2 text-[9px] tracking-[0.12em] text-shell/40">ENGINE RULE · {ruleIds.join(" · ")}</p>}
        </Section>

        <Section title="SOURCES">
          <ul className="mt-1 space-y-1 text-[10px] leading-snug text-shell/60">
            {guide.sources.map((id) => <li key={id}>· {SOURCES[id]?.title ?? id}</li>)}
            <li className="text-shell/40">· {guide.assumption}</li>
          </ul>
        </Section>
      </div>

      <footer className="border-t border-pulse/20 px-4 py-2 text-[10px] uppercase tracking-[0.2em] text-orbit">{NOTICE}</footer>
    </aside>
  );
}
