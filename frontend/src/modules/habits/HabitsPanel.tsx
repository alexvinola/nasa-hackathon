"use client";

import { useEffect, useState } from "react";
import { useT } from "@/i18n";
import { HudPanel } from "@/modules/hud/HudPanel";
import { BADGES, dayKey, HABITS, history, levelOf, pending, progress, streak, totalXp, XP_PER_LEVEL, type HabitId } from "./habits";
import { logHabit, useHabitLog } from "./habitStore";

/** Seven bars, one per day, against the daily target line; green when the target was reached. */
function Histogram({ id, log }: { id: HabitId; log: ReturnType<typeof useHabitLog> }) {
  const habit = HABITS.find((item) => item.id === id)!;
  const days = history(log, id, new Date());
  const max = Math.max(habit.target * 1.25, ...days.map((day) => day.value));
  return (
    <div data-habit-histogram={id} className="relative mt-2 flex h-20 items-end gap-1 border-b border-shell/30">
      <div aria-hidden className="absolute inset-x-0 border-t border-dashed border-pulse/60" style={{ bottom: `${(habit.target / max) * 100}%` }} />
      {days.map((day) => (
        <div key={day.key} className="flex h-full flex-1 flex-col justify-end" title={`${day.key}: ${day.value}`}>
          <div
            data-bar={day.key}
            className={`w-full ${day.value >= habit.target ? "bg-emerald-400" : day.value > 0 ? "bg-amber-400" : "bg-shell/15"}`}
            style={{ height: `${Math.max((day.value / max) * 100, day.value > 0 ? 4 : 2)}%` }}
          />
        </div>
      ))}
    </div>
  );
}

/**
 * Daily habits as a game: a bar per habit with a "+" to log it, a 7-day histogram of the selected one, XP, level,
 * streak and badges. A reminder appears for every habit whose hour has passed and whose target is not reached.
 */
export function HabitsPanel() {
  const t = useT();
  const log = useHabitLog();
  const [selected, setSelected] = useState<HabitId>("exercise");
  // The clock only matters for the reminders, so it ticks once a minute (and starts after hydration).
  const [now, setNow] = useState<Date | null>(null);
  useEffect(() => {
    setNow(new Date());
    const id = setInterval(() => setNow(new Date()), 60_000);
    return () => clearInterval(id);
  }, []);
  const today = now ?? new Date(0);
  const due = now ? pending(log, now) : [];
  const xp = totalXp(log);
  const days = streak(log, today);
  const today_ = log[dayKey(today)] ?? {};

  return (
    <HudPanel data-habits title={<span className={due.length ? "animate-pulse text-amber-300" : ""}>{t("habits.title")}{due.length ? ` · ${due.length}` : ""}</span>} defaultOpen={false}>
      <p className="flex justify-between text-shell">
        <span>{t("habits.level", { level: levelOf(xp) })}</span>
        <span>{t("habits.streak", { days })}</span>
      </p>
      <div className="mt-1 h-1.5 bg-shell/15">
        <div className="h-full bg-pulse" style={{ width: `${((xp % XP_PER_LEVEL) / XP_PER_LEVEL) * 100}%` }} />
      </div>
      <p className="mt-0.5 text-[10px] text-shell/60">{t("habits.xp", { xp: xp % XP_PER_LEVEL, next: XP_PER_LEVEL })}</p>

      {due.map((habit) => (
        <p key={habit.id} role="alert" data-habit-reminder={habit.id} className="mt-2 border border-amber-400 bg-amber-400/10 p-1.5 normal-case tracking-normal text-amber-200">
          {t("habits.remind", { habit: t(habit.title), left: Math.round((habit.target - (today_[habit.id] ?? 0)) * 10) / 10, unit: t(habit.unit) })}
        </p>
      ))}

      <ul className="mt-2 space-y-1.5">
        {HABITS.map((habit) => {
          const value = today_[habit.id] ?? 0;
          return (
            <li key={habit.id} className="flex items-center gap-2">
              <button
                type="button"
                data-habit-select={habit.id}
                aria-pressed={selected === habit.id}
                onClick={() => setSelected(habit.id)}
                className={`pointer-events-auto flex-1 text-left ${selected === habit.id ? "text-pulse" : "text-shell/80"}`}
              >
                <span className="flex justify-between">
                  <span>{t(habit.title)}</span>
                  <span>
                    {value} / {habit.target} {t(habit.unit)}
                  </span>
                </span>
                <span className="mt-0.5 block h-1 bg-shell/15">
                  <span className={`block h-full ${value >= habit.target ? "bg-emerald-400" : "bg-pulse"}`} style={{ width: `${progress(habit, value) * 100}%` }} />
                </span>
              </button>
              <button
                type="button"
                data-habit-add={habit.id}
                aria-label={t("habits.add", { habit: t(habit.title) })}
                onClick={() => logHabit(habit.id, habit.step)}
                className="pointer-events-auto border border-pulse/50 px-1.5 text-pulse hover:bg-pulse/20"
              >
                +
              </button>
            </li>
          );
        })}
      </ul>

      <Histogram id={selected} log={log} />
      <p className="mt-0.5 text-[10px] text-shell/60">{t("habits.histogram", { habit: t(HABITS.find((item) => item.id === selected)!.title) })}</p>

      <p className="mt-2 flex flex-wrap gap-1">
        {BADGES.map((badge) => (
          <span key={badge.id} data-badge={badge.id} className={`border px-1.5 py-0.5 ${badge.earned(log, days) ? "border-emerald-400 text-emerald-300" : "border-shell/20 text-shell/40"}`}>
            {t(badge.label)}
          </span>
        ))}
      </p>
      <p className="mt-2 text-[10px] normal-case leading-snug tracking-normal text-shell/60">{t("habits.note")}</p>
    </HudPanel>
  );
}
