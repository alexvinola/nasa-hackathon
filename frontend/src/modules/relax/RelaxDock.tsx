"use client";

import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { useT } from "@/i18n";
import { logHabit } from "@/modules/habits/habitStore";
import { LEFT_COLUMN_ID } from "@/modules/hud/HudPanel";
import { useHudAction } from "@/modules/hud/hudActions";
import { useHotkey } from "@/modules/hud/useHotkey";
import { EXERCISES, position, totalSeconds, type Exercise } from "./exercises";
import { Cue, Orb, RelaxBackdrop } from "./RelaxScene";
import { useRelaxReminder } from "./useRelaxReminder";

const BTN = "border-2 px-4 py-2 text-sm font-bold tracking-[0.12em] hover:border-shell";

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
  const cycle = Math.floor(elapsed / exercise.phases.reduce((sum, item) => sum + item.seconds, 0)); // which round, so a repeated phase restarts its bar
  return (
    <div data-relax-session={exercise.id} className="flex w-full max-w-3xl flex-1 flex-col items-center justify-center gap-8">
      <div className="relative grid place-items-center">
        <Orb mood={exercise.id} scale={phase?.scale ?? 0.4} seconds={phase?.seconds ?? 1} />
        {phase && <Cue key={`${cycle}-${phase.key}`} phase={phase.key} />}
      </div>
      <p role="status" className="min-h-16 text-center text-4xl font-light normal-case tracking-wide text-white drop-shadow-[0_0_12px_rgba(255,255,255,0.35)]">
        {phase ? t(phase.key) : ""} {!now.done && <span className="text-pulse">· {now.left}s</span>}
      </p>
      {/* The bar fills in exactly the seconds of the phase it belongs to. */}
      <div className="h-1.5 w-full max-w-xl overflow-hidden rounded bg-white/15">
        {phase && <div key={`${cycle}-${phase.key}`} className="relax-anim h-full bg-white/80" style={{ animation: `relax-fill ${phase.seconds}s linear forwards` }} />}
      </div>
      <button type="button" onClick={() => onEnd(false)} className={`${BTN} border-shell/40 text-shell/80`}>
        {t("relax.stop")}
      </button>
    </div>
  );
}

/**
 * Relaxation exercises on the whole screen, and the reminder that offers them every half hour. A small RELAJARSE button
 * opens them; when the reminder is due a banner offers to start one now or later. `suggest` is true while the rules
 * engine finds the astronaut drowsy.
 */
export function RelaxDock({ suggest = false }: { suggest?: boolean }) {
  const t = useT();
  const [open, setOpen] = useState(false);
  const [exercise, setExercise] = useState<Exercise | null>(null);
  const reminder = useRelaxReminder(open);
  // The RELAX button joins the stack of panels on the left, above the rest, so it moves with them.
  const [column, setColumn] = useState<HTMLElement | null>(null);
  useEffect(() => setColumn(document.getElementById(LEFT_COLUMN_ID)), []);
  // PULSAR was asked to open the relaxation menu, or to put one exercise on.
  useHudAction((action) => {
    if (action.type !== "open_relax") return;
    const picked = EXERCISES.find((item) => item.id === action.exercise);
    if (picked) start(picked);
    else {
      setExercise(null);
      setOpen(true);
    }
  });
  useHotkey("escape", () => {
    if (open) {
      setExercise(null);
      setOpen(false);
    }
  });

  const start = (picked: Exercise) => {
    setExercise(picked);
    setOpen(true);
  };
  const end = (finished: boolean) => {
    setExercise(null);
    if (finished) {
      reminder.done();
      logHabit("relax", 1);
    }
  };

  return (
    <>
      <div data-hud-panel data-relax className="pointer-events-none absolute bottom-24 left-[19rem] z-10 w-80 text-sm tracking-[0.1em] text-shell/80">
        {reminder.due && !open && (
          <div role="alert" data-relax-due className="pointer-events-auto w-80 border-2 border-pulse bg-space/90 p-3 backdrop-blur">
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
      </div>
      {column &&
        createPortal(
          <button
            type="button"
            data-hud-panel
            data-relax-open
            aria-expanded={open}
            onClick={() => setOpen(true)}
            className={`${BTN} pointer-events-auto order-first mt-auto block w-full shrink-0 border-pulse/60 bg-space/60 text-pulse backdrop-blur ${suggest || reminder.due ? "animate-pulse border-amber-400 text-amber-300" : ""}`}
          >
            {t("relax.open")}
          </button>,
          column,
        )}

      {open && (
        <RelaxBackdrop mood={exercise?.id ?? "menu"}>
        <section role="dialog" aria-modal="true" aria-label={t("relax.aria")} className="flex w-full flex-1 flex-col items-center gap-6">
          <header className="flex w-full items-start justify-between gap-8">
            <h1 className="text-2xl font-bold tracking-[0.2em] text-pulse">{t("relax.heading")}</h1>
            <button type="button" onClick={() => { setExercise(null); setOpen(false); }} className={`${BTN} border-shell/40 text-shell/80`}>
              {t("relax.close")}
            </button>
          </header>
          {suggest && !exercise && <p className="text-xl normal-case tracking-normal text-amber-300">{t("relax.suggest")}</p>}
          {exercise ? (
            <Session exercise={exercise} onEnd={end} />
          ) : (
            <div className="flex w-full max-w-5xl flex-1 flex-col justify-center gap-6">
              <ul className="grid gap-6 md:grid-cols-3">
                {EXERCISES.map((item) => (
                  <li key={item.id}>
                    <button
                      type="button"
                      data-relax-start={item.id}
                      onClick={() => start(item)}
                      className="h-full w-full rounded-3xl border border-white/20 bg-white/5 p-8 text-left text-2xl font-bold text-white backdrop-blur-md transition hover:border-white/50 hover:bg-white/10"
                    >
                      {t(item.title)}
                      <span className="mt-3 block text-base font-normal normal-case leading-snug tracking-normal text-shell/80">{t(item.hint)}</span>
                    </button>
                  </li>
                ))}
              </ul>
              <p className="text-center text-sm normal-case leading-snug tracking-normal text-shell/60">{t("relax.note")}</p>
            </div>
          )}
        </section>
        </RelaxBackdrop>
      )}
    </>
  );
}
