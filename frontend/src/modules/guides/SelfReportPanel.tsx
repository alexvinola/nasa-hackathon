"use client";

import { useEffect, useRef, useState } from "react";
import { GuideAnimation } from "./GuideAnimation";
import { GUIDES, localizedGuide, type GuideStatus } from "./guides";
import { useLang, useT, type Key } from "@/i18n";
import { entered, FIELDS, isValid, REFERENCES, type Entries, type Field } from "./selfReport";

const TONE: Record<GuideStatus, string> = {
  GREEN: "border-emerald-400 text-emerald-300",
  AMBER: "border-amber-400 text-amber-300",
  RED: "border-red-500 text-red-300",
  "NOT JUDGED": "border-orbit text-orbit",
  WAITING: "border-shell/40 text-shell/70",
};
const STEP_EVERY_MS = 4000;

/** Only digits get in (typed or pasted); a field that takes tenths also takes one decimal separator. */
const digitsOnly = (f: Field, raw: string) => {
  const kept = raw.replace(/[^0-9.,]/g, "");
  if (f.step >= 1) return kept.replace(/[.,]/g, "");
  const at = kept.search(/[.,]/);
  return at < 0 ? kept : kept.slice(0, at + 1) + kept.slice(at + 1).replace(/[.,]/g, "");
};

const shown = (f: Field, value: number) => (f.step < 1 ? value.toFixed(1) : String(value));

/**
 * Where the astronaut types in what the devices read, one measurement at a time: the picture and the steps of how
 * to use the device on the left, the number on the right. ENTER saves and moves to the next one, so the whole round
 * can be done from the keyboard. A saved value goes to the rules engine with the next evaluation; this panel never
 * judges it, it only shows the engine's status for it.
 */
export function SelfReportPanel({
  entries,
  statuses,
  signal,
  onSelect,
  valueOf,
  onSave,
  onClear,
  onClose,
}: {
  entries: Entries;
  statuses: Record<string, GuideStatus>;
  /** The measurement a body marker asked for; the form moves to it, and reports the tab it is on. */
  signal?: string | null;
  onSelect?: (signal: string) => void;
  /** The reading the HUD has now for a measurement, as text ("72 bpm"). */
  valueOf?: (signal: string) => string;
  onSave: (values: Entries) => void;
  onClear: (keys: string[]) => void;
  onClose: () => void;
}) {
  const [at, setAt] = useState(() => {
    const asked = GUIDES.findIndex((guide) => guide.signal === signal);
    return asked >= 0 ? asked : Math.max(0, GUIDES.findIndex((guide) => !entered(guide.signal, entries)));
  });
  useEffect(() => {
    const asked = GUIDES.findIndex((guide) => guide.signal === signal);
    if (asked >= 0) setAt(asked);
  }, [signal]);
  const mounted = useRef(false);
  useEffect(() => {
    if (mounted.current) onSelect?.(GUIDES[at].signal);
    mounted.current = true;
  }, [at]); // eslint-disable-line react-hooks/exhaustive-deps
  const t = useT();
  const lang = useLang();
  const guide = localizedGuide(GUIDES[at], lang);
  const label = (f: Field) => t(`selfReport.field.${f.key}` as Key);
  const unit = (f: Field) => (f.unit.startsWith("selfReport.") ? t(f.unit as Key) : f.unit);
  const fields = FIELDS[guide.signal];
  const [draft, setDraft] = useState<Record<string, string>>({});
  const [step, setStep] = useState(0);
  const [auto, setAuto] = useState(true); // the steps loop until the astronaut picks one
  const [info, setInfo] = useState(false); // the reference, why it matters and what to do: behind the "i" button
  const first = useRef<HTMLInputElement>(null);

  // A new measurement starts from what was saved for it, with the cursor in its first field.
  useEffect(() => {
    setDraft(Object.fromEntries(fields.filter((f) => f.key in entries).map((f) => [f.key, shown(f, entries[f.key])])));
    setStep(0);
    setAuto(true);
    first.current?.focus();
    first.current?.select();
  }, [at]); // eslint-disable-line react-hooks/exhaustive-deps

  // The how-to steps play in a loop beside the picture, as in the guide; never under reduced motion.
  useEffect(() => {
    if (!auto || matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const id = setInterval(() => setStep((current) => (current + 1) % guide.how.length), STEP_EVERY_MS);
    return () => clearInterval(id);
  }, [guide.how.length, at, auto]);

  const numbers = Object.fromEntries(fields.map((f) => [f.key, Number((draft[f.key] ?? "").replace(",", "."))]));
  const filled = fields.every((f) => (draft[f.key] ?? "").trim() !== "");
  const ready = filled && fields.every((f) => isValid(f, numbers[f.key]));
  const done = GUIDES.filter((candidate) => entered(candidate.signal, entries)).length;

  const save = () => {
    if (!ready) return;
    onSave(numbers);
    setAt((current) => (current + 1) % GUIDES.length);
  };
  const nudge = (f: Field, by: number) => {
    const from = Number.isFinite(numbers[f.key]) && (draft[f.key] ?? "") !== "" ? numbers[f.key] : by > 0 ? f.min : f.max;
    const next = Math.min(f.max, Math.max(f.min, Math.round((from + by) / f.step) * f.step));
    setDraft((had) => ({ ...had, [f.key]: shown(f, next) }));
  };

  return (
    <section
      data-hud-panel
      data-self-report
      data-guide={signal === guide.signal ? guide.signal : undefined}
      aria-label={t("selfReport.aria")}
      onKeyDown={(event) => event.key === "Escape" && onClose()}
      className="fixed inset-2 z-20 flex flex-col overflow-hidden border-2 border-pulse/60 bg-space/90 text-sm text-shell backdrop-blur md:absolute md:inset-auto md:left-[19rem] md:top-24 md:z-10 md:max-h-[calc(100vh-17rem)] md:w-[46rem] md:max-w-[calc(100vw-22rem)] md:bg-space/80"
    >
      <header className="flex items-start gap-3 shrink-0 border-b border-pulse/30 px-4 py-3">
        <div>
          <h2 className="text-lg tracking-[0.15em] text-pulse">{t("selfReport.title")}</h2>
          <p className="text-xs tracking-[0.1em] text-shell/70">
            {t("selfReport.progress", { done, total: GUIDES.length })}
          </p>
        </div>
        <button type="button" onClick={onClose} className="ml-auto border border-shell/40 px-2 py-1 text-xs tracking-[0.15em] text-shell/80 hover:border-shell">
          {t("selfReport.close")}
        </button>
      </header>
      <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain p-4">

      {/* One tab per measurement: the saved value and the engine's status for it, at a glance. */}
      <nav className="mt-3 grid grid-cols-3 gap-2" aria-label={t("selfReport.tabs")}>
        {GUIDES.map((raw, index) => {
          const candidate = localizedGuide(raw, lang);
          const saved = entered(candidate.signal, entries);
          const status = statuses[candidate.signal] ?? "WAITING";
          return (
            <button
              key={candidate.signal}
              type="button"
              data-self-report-tab={candidate.signal}
              aria-current={index === at ? "true" : undefined}
              onClick={() => setAt(index)}
              className={`border px-2 py-1.5 text-left text-xs leading-tight ${index === at ? "border-pulse bg-pulse/15" : "border-shell/30 hover:border-shell/60"}`}
            >
              <span className="block tracking-[0.1em] text-shell">{candidate.label.toUpperCase()}</span>
              <span className={saved ? "text-shell/90" : "text-shell/50"}>
                {saved ? FIELDS[candidate.signal].map((f) => shown(f, entries[f.key])).join("/") + " " + unit(FIELDS[candidate.signal][0]) : t("selfReport.notEntered")}
              </span>
              {saved && <span className={`ml-2 border px-1 text-[10px] ${TONE[status]}`}>{t(`selfReport.status.${status}` as Key)}</span>}
            </button>
          );
        })}
      </nav>

      <div className="mt-4 flex flex-col gap-4 sm:flex-row">
        <div className="w-full shrink-0 sm:w-64">
          <GuideAnimation key={guide.signal} signal={guide.signal} focus={guide.how[Math.min(step, guide.how.length - 1)].focus} label={guide.label} />
          <p className="mt-1 text-xs tracking-[0.1em] text-shell/70">{guide.instrument}</p>
          <dl className="mt-2 text-xs tracking-[0.1em] text-shell/70">
            <dt>{t("guides.panel.now")}</dt>
            <dd data-guide-value className="text-xl tracking-normal text-shell">{valueOf?.(guide.signal)}</dd>
            <dt className="mt-1">{t("guides.panel.engine")}</dt>
            <dd data-guide-status className={`mt-1 inline-block border px-2 py-0.5 text-sm ${TONE[statuses[guide.signal] ?? "WAITING"]}`}>{t(`guides.verdict.${statuses[guide.signal] ?? "WAITING"}` as Key)}</dd>
          </dl>
        </div>

        <div className="min-w-0 flex-1">
          <h3 className="text-xs tracking-[0.15em] text-orbit">{t("selfReport.how")}</h3>
          <ol className="mt-1 space-y-0.5">
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
                  className={`flex w-full gap-2 border px-2 py-0.5 text-left text-[13px] leading-snug ${index === step ? "border-pulse bg-pulse/15 text-shell" : "border-transparent text-shell/70 hover:border-shell/30"}`}
                >
                  <span className="text-pulse">{index + 1}.</span>
                  <span>{item.text}</span>
                </button>
              </li>
            ))}
          </ol>
        </div>
      </div>

      <form
        className="mt-4 border-t border-pulse/20 pt-3"
        onSubmit={(event) => {
          event.preventDefault();
          save();
        }}
      >
        <h3 className="text-xs tracking-[0.15em] text-orbit">{t("selfReport.reading")}</h3>
        <div className="mt-2 flex flex-wrap items-end gap-4">
          {fields.map((f, index) => {
            const text = draft[f.key] ?? "";
            const wrong = text.trim() !== "" && !isValid(f, numbers[f.key]);
            return (
              <label key={f.key} className="block">
                <span className="block text-xs tracking-[0.1em] text-shell/80">{label(f).toUpperCase()}</span>
                <span className="mt-1 flex items-center gap-1">
                  <button type="button" tabIndex={-1} aria-label={t("selfReport.lower", { label: label(f) })} onClick={() => nudge(f, -f.step)} className="h-12 w-10 border border-shell/40 text-2xl text-shell/80 hover:border-shell">
                    −
                  </button>
                  <input
                    ref={index === 0 ? first : undefined}
                    data-self-report-field={f.key}
                    inputMode={f.step < 1 ? "decimal" : "numeric"}
                    autoComplete="off"
                    value={text}
                    aria-invalid={wrong}
                    onChange={(event) => setDraft((had) => ({ ...had, [f.key]: digitsOnly(f, event.target.value) }))}
                    onKeyDown={(event) => {
                      if (event.key === "ArrowUp" || event.key === "ArrowDown") {
                        event.preventDefault();
                        nudge(f, event.key === "ArrowUp" ? f.step : -f.step);
                      }
                    }}
                    className={`h-12 w-28 border-2 bg-space px-2 text-center text-3xl text-shell outline-none ${wrong ? "border-red-500" : "border-pulse/60 focus:border-pulse"}`}
                  />
                  <button type="button" tabIndex={-1} aria-label={t("selfReport.raise", { label: label(f) })} onClick={() => nudge(f, f.step)} className="h-12 w-10 border border-shell/40 text-2xl text-shell/80 hover:border-shell">
                    +
                  </button>
                  <span className="ml-1 text-shell/70">{unit(f)}</span>
                </span>
                <span className={`mt-1 block text-[11px] ${wrong ? "text-red-300" : "text-shell/50"}`}>
                  {t(wrong ? "selfReport.wrong" : "selfReport.accepts", { min: f.min, max: f.max })}
                </span>
              </label>
            );
          })}
          <button type="submit" disabled={!ready} className="h-12 border-2 border-pulse bg-pulse/20 px-5 text-base font-bold tracking-[0.1em] text-pulse disabled:border-shell/30 disabled:bg-transparent disabled:text-shell/40">
            {t("selfReport.save")}
          </button>
          {entered(guide.signal, entries) && (
            <button type="button" onClick={() => onClear(fields.map((f) => f.key))} className="h-12 text-xs text-shell/60 underline">
              {t("selfReport.clear")}
            </button>
          )}
        </div>
      </form>

      <button
        type="button"
        data-self-report-info
        aria-expanded={info}
        aria-controls="self-report-info"
        onClick={() => setInfo((was) => !was)}
        className="mt-3 flex items-center gap-2 text-xs tracking-[0.12em] text-pulse hover:text-shell"
      >
        <span aria-hidden className={`grid h-5 w-5 place-items-center rounded-full border text-[11px] font-bold italic ${info ? "border-pulse bg-pulse/20" : "border-pulse/60"}`}>i</span>
        {t(info ? "selfReport.infoLess" : "selfReport.info")}
      </button>

      <div id="self-report-info" hidden={!info}>
      <aside data-self-report-reference className="mt-3 border border-orbit/40 bg-orbit/5 px-3 py-2 text-[13px] leading-snug">
        <h3 className="text-xs tracking-[0.15em] text-orbit">{t("selfReport.ref.title")}</h3>
        {REFERENCES[guide.signal].length === 0 && <p className="mt-1 text-shell/80">{t("selfReport.ref.none")}</p>}
        {REFERENCES[guide.signal].map((reference) => (
          <p key={reference.text} className="mt-1 text-shell">
            {t(reference.text as Key)}{" "}
            <span className="text-[11px] text-shell/60">
              ({t(reference.flight ? "selfReport.ref.flight" : "selfReport.ref.earth")} · {reference.source})
            </span>
          </p>
        ))}
      </aside>

      <h3 className="mt-3 text-xs tracking-[0.15em] text-orbit">{t("guides.panel.why")}</h3>
      <p className="mt-1 leading-snug">{guide.why}</p>
      <h3 className="mt-3 text-xs tracking-[0.15em] text-orbit">{t("guides.panel.abnormal")}</h3>
      <p className="mt-1 leading-snug">{guide.whenAbnormal.text}</p>
      {guide.whenAbnormal.countermeasureIds.length > 0 && (
        // Rule ids stay out of sight: some carry their limit in the name, and a guide quotes no threshold.
        <p className="mt-1 text-xs text-shell/60">{t("guides.panel.countermeasure", { ids: guide.whenAbnormal.countermeasureIds.join(", ") })}</p>
      )}

      <p className="mt-3 border-t border-pulse/20 pt-2 text-[11px] tracking-[0.1em] text-shell/60">
        {t("selfReport.footer")} · {t("guides.panel.sources", { sources: guide.sources.join(", ") })}
        {guide.assumption ? t("guides.panel.teamSteps") : ""}
      </p>
      </div>

      <p className="mt-3 border-t border-pulse/20 pt-2 text-[11px] tracking-[0.1em] text-orbit">NOT A MEDICAL DEVICE</p>
      </div>
    </section>
  );
}
