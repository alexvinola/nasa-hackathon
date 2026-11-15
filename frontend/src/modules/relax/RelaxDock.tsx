"use client";

import { useEffect, useState } from "react";
import { useT } from "@/i18n";
import { EXERCISES, REMINDER_OPTIONS, position, totalSeconds, type Exercise } from "./exercises";
import { useRelaxReminder } from "./useRelaxReminder";

const BTN = "border px-3 py-1.5 text-xs tracking-[0.12em] hover:border-shell";

/** The guide circle of a running exercise: it grows and shrinks over each phase, with the instruction and the seconds left. */
function Session({ exercise, onEnd }: { exercise: Exercise; onEnd: (finished: boolean) => void }) {
  const t = useT();
  const [elapsed, setElapsed] = useState(0);
  useEffect(() => {
    const id = setInterval(() => setElapsed((seconds) => seconds + 1), 1000);
    return () => clearInterval(id);
  }, []);
  const now = position(exercise, elapsed);
  useEffect(() => {
    if (now.done) onEnd(true);
  }, [now.done, onEnd]);
  const phase = now.done ? null : now.phase;
  return (
    <div data-relax-session={exercise.id} className="mt-3 flex flex-col items-center gap-3">
      <div className="grid h-32 w-32 place-items-center">
        <div
          aria-hidden
          className="h-32 w-32 rounded-full border-2 border-pulse bg-pulse/20 shadow-[0_0_24px] shadow-pulse/40"
          style={{ transform: `scale(${phase?.scale ?? 0.4})`, transition: `transform ${phase?.seconds ?? 1}s ease-in-out` }}
        />
      </div>
      <p role="status" className="min-h-10 text-center text-base normal-case tracking-normal text-shell">
        {phase ? t(phase.key) : ""} {!now.done && <span className="text-pulse">· {now.left}s</span>}
      </p>
      <div className="h-1 w-full overflow-hidden rounded bg-shell/15">
        <div className="h-full bg-pulse transition-[width] duration-1000 ease-linear" style={{ width: `${Math.min(100, (elapsed / totalSeconds(exercise)) * 100)}%` }} />
      </div>
      <button type="button" onClick={() => onEnd(false)} className={`${BTN} border-shell/40 text-shell/80`}>
        {t("relax.stop")}
      </button>
    </div>
  );
}

/**
 * Relaxation buttons and the reminder. A small RELAJARSE button opens the exercises; when the reminder is due a banner
 * offers to start one now or later. `suggest` is true while the rules engine finds the astronaut drowsy.
 */
export function RelaxDock({ suggest = false }: { suggest?: boolean }) {
  const t = useT();
  const [open, setOpen] = useState(false);
  const [exercise, setExercise] = useState<Exercise | null>(null);
  const reminder = useRelaxReminder(exercise !== null);

  const start = (picked: Exercise) => {
    setExercise(picked);
    setOpen(true);
  };
  const end = (finished: boolean) => {
    setExercise(null);
    if (finished) reminder.done();
  };

  return (
    <div data-hud-panel data-relax className="pointer-events-none absolute bottom-16 right-8 z-10 w-80 text-sm tracking-[0.1em] text-shell/80">
      {reminder.due && !exercise && (
        <div role="alert" data-relax-due className="pointer-events-auto absolute bottom-0 right-[21rem] w-80 border-2 border-pulse bg-space/90 p-3 backdrop-blur">
          <p className="text-base normal-case tracking-normal text-shell">{t("relax.due")}</p>
          <div className="mt-2 flex gap-2">
            <button type="button" onClick={() => start(EXERCISES[0])} className={`${BTN} border-pulse bg-pulse/20 text-pulse`}>
              {t("relax.start")}
            </button>
            <button type="button" onClick={reminder.snooze} className={`${BTN} border-shell/40 text-shell/80`}>
              {t("relax.later")}
            </button>
          </div>
        </div>
      )}

      {open && (
        <section aria-label={t("relax.aria")} className="pointer-events-auto absolute bottom-0 right-[21rem] z-10 w-80 rounded-lg border border-pulse/40 bg-space/80 p-3 backdrop-blur">
          <h2 className="text-xs tracking-[0.15em] text-orbit">{t("relax.heading")}</h2>
          {suggest && !exercise && <p className="mt-1 text-sm normal-case tracking-normal text-amber-300">{t("relax.suggest")}</p>}
          {exercise ? (
            <Session exercise={exercise} onEnd={end} />
          ) : (
            <>
              <ul className="mt-2 space-y-2">
                {EXERCISES.map((item) => (
                  <li key={item.id}>
                    <button type="button" data-relax-start={item.id} onClick={() => start(item)} className={`${BTN} w-full border-pulse/50 text-left text-pulse`}>
                      {t(item.title)}
                      <span className="mt-0.5 block text-[11px] normal-case tracking-normal text-shell/70">{t(item.hint)}</span>
                    </button>
                  </li>
                ))}
              </ul>
              <label className="mt-3 flex items-center justify-between gap-2 text-xs">
                {t("relax.remind")}
                <select
                  value={reminder.every}
                  onChange={(event) => reminder.setEvery(Number(event.target.value) as (typeof REMINDER_OPTIONS)[number])}
                  className="border border-shell/40 bg-space px-2 py-1 text-shell"
                >
                  {REMINDER_OPTIONS.map((minutes) => (
                    <option key={minutes} value={minutes}>
                      {minutes === 0 ? t("relax.off") : minutes === 1 ? t("relax.test") : t("relax.minutes", { minutes })}
                    </option>
                  ))}
                </select>
              </label>
              <p className="mt-2 text-[11px] normal-case leading-snug tracking-normal text-shell/60">{t("relax.note")}</p>
            </>
          )}
        </section>
      )}

      <button
        type="button"
        aria-expanded={open}
        onClick={() => setOpen((was) => !was)}
        className={`${BTN} pointer-events-auto ml-auto block border-pulse/60 bg-space/80 text-pulse ${suggest || reminder.due ? "animate-pulse border-amber-400 text-amber-300" : ""}`}
      >
        {t("relax.open")}
      </button>
    </div>
  );
}
