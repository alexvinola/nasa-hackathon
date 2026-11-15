"use client";

import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { useLang, useT, type Key } from "@/i18n";
import { HudPanel } from "@/modules/hud/HudPanel";
import { useHudAction } from "@/modules/hud/hudActions";
import { BADGES, dayKey, dayScore, daysBack, GOOD_DAY, habitStats, HABITS, history, levelOf, pending, progress, range, streak, totalXp, XP_PER_LEVEL, type HabitId } from "./habits";
import { logHabit, setHabit, useHabitLog } from "./habitStore";

/** One bar per day for the last `n` days, against the daily target line; green when the target was reached. */
function Histogram({ id, log, n }: { id: HabitId; log: ReturnType<typeof useHabitLog>; n: number }) {
  const habit = HABITS.find((item) => item.id === id)!;
  const days = history(log, id, new Date(), n);
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

const input = (date: Date) => dayKey(date);
const parse = (text: string) => {
  const [y, m, d] = text.split("-").map(Number);
  return new Date(y, m - 1, d);
};
const percent = (n: number) => Math.round(n * 100);
const tone = (score: number) => (score >= GOOD_DAY ? "bg-emerald-400" : score > 0 ? "bg-amber-400" : "bg-shell/15");
const CARD = "border border-pulse/20 bg-space/40 p-3";

/** Longest run of good days inside a range. */
function bestRun(days: ReturnType<typeof range>) {
  let best = 0;
  let run = 0;
  for (const day of days) {
    run = day.score >= GOOD_DAY ? run + 1 : 0;
    best = Math.max(best, run);
  }
  return best;
}

/** The month, or any range up to a year: key figures, the daily score, every habit on its own and the weekdays. */
function Expanded({ log, today, onClose }: { log: ReturnType<typeof useHabitLog>; today: Date; onClose: () => void }) {
  const t = useT();
  const lang = useLang();
  const [from, setFrom] = useState(input(daysBack(today, 29)));
  const [to, setTo] = useState(input(today));
  const days = range(log, parse(from), parse(to));
  const n = days.length;
  const good = days.filter((day) => day.score >= GOOD_DAY).length;
  const average = n ? days.reduce((sum, day) => sum + day.score, 0) / n : 0;
  const best = days.reduce<(typeof days)[number] | null>((top, day) => (!top || day.score > top.score ? day : top), null);
  // The same number of days right before the range, to say whether this one is better.
  const before = n ? range(log, daysBack(parse(from), n), daysBack(parse(from), 1)) : [];
  const beforeHasData = before.filter((day) => day.score > 0).length >= n / 2 // a thin previous period would make the comparison misleading;
  const delta = beforeHasData ? percent(average) - percent(before.reduce((sum, day) => sum + day.score, 0) / before.length) : null;
  const locale = lang === "es" ? "es-ES" : "en-US";
  const weekday = (date: Date) => date.toLocaleDateString(locale, { weekday: "short" });
  const byWeekday = Array.from({ length: 7 }, (_, i) => {
    const mine = days.filter((day) => (day.date.getDay() + 6) % 7 === i);
    return { name: weekday(new Date(2024, 0, 1 + i)), score: mine.length ? mine.reduce((sum, day) => sum + day.score, 0) / mine.length : null };
  });
  const scored = byWeekday.filter((day) => day.score !== null);
  const bestWeekday = scored.reduce<(typeof scored)[number] | null>((top, day) => (!top || day.score! > top.score! ? day : top), null);
  const worstWeekday = scored.reduce<(typeof scored)[number] | null>((low, day) => (!low || day.score! < low.score! ? day : low), null);
  const quick = (count: number) => {
    setFrom(input(daysBack(today, count - 1)));
    setTo(input(today));
  };
  const active = (count: number) => to === input(today) && from === input(daysBack(today, count - 1));
  const short = (key: string) => key.slice(5).replace("-", "/");

  return (
    <div data-habits-expanded role="dialog" aria-modal="true" aria-label={t("habits.expanded.title")} className="pointer-events-auto fixed inset-0 z-30 grid place-items-center bg-space/40 p-4" onKeyDown={(event) => event.key === "Escape" && onClose()} onClick={(event) => event.target === event.currentTarget && onClose()}>
      <section className="flex max-h-full w-[60rem] max-w-full flex-col overflow-hidden border-2 border-pulse/60 bg-space/90 text-sm normal-case tracking-normal text-shell backdrop-blur md:bg-space/70">
        <header className="flex items-start gap-3 shrink-0 border-b border-pulse/30 px-4 py-3">
          <div>
            <h2 className="text-lg tracking-[0.18em] text-pulse">{t("habits.expanded.title")}</h2>
            <p className="mt-0.5 text-xs text-shell/60">{t("habits.rangeOf", { n, from: short(from), to: short(to) })}</p>
          </div>
          <button type="button" autoFocus onClick={onClose} aria-label={t("habits.close")} title={t("habits.close")} className="ml-auto border border-shell/40 px-2 py-1 text-xs leading-none text-shell/80 hover:border-pulse hover:text-pulse">✕</button>
        </header>
        <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain p-4">

        <div className="mt-4 flex flex-wrap items-center gap-2 text-xs">
          {[7, 30, 60].map((count) => (
            <button key={count} type="button" aria-pressed={active(count)} onClick={() => quick(count)} className={`border px-3 py-1 ${active(count) ? "border-pulse bg-pulse/20 text-pulse" : "border-shell/25 text-shell/70 hover:border-pulse/60"}`}>{count} d</button>
          ))}
          <span className="ml-auto flex items-center gap-2 text-shell/70">
            <label>{t("habits.from")} <input type="date" value={from} max={to} onChange={(e) => e.target.value && setFrom(e.target.value)} className="border border-shell/30 bg-space/80 px-2 py-1 text-shell [color-scheme:dark]" /></label>
            <label>{t("habits.to")} <input type="date" value={to} min={from} max={input(today)} onChange={(e) => e.target.value && setTo(e.target.value)} className="border border-shell/30 bg-space/80 px-2 py-1 text-shell [color-scheme:dark]" /></label>
          </span>
        </div>

        {n === 0 ? (
          <p className="mt-6 text-shell/60">{t("habits.noData")}</p>
        ) : (
          <>
            <div data-habits-kpis className="mt-4 grid grid-cols-2 gap-3 md:grid-cols-4">
              <div className={CARD}>
                <p className="text-xs uppercase tracking-[0.15em] text-shell/60">{t("habits.kpi.avg")}</p>
                <p className="mt-1 text-3xl font-semibold text-pulse">{percent(average)}<span className="text-lg"> %</span></p>
                <p className={`mt-0.5 text-xs ${delta === null ? "text-shell/60" : delta >= 0 ? "text-emerald-300" : "text-amber-300"}`}>
                  {delta === null ? t("habits.noPrev") : t("habits.vsPrev", { delta: `${delta >= 0 ? "▲ +" : "▼ "}${delta}` })}
                </p>
              </div>
              <div className={CARD}>
                <p className="text-xs uppercase tracking-[0.15em] text-shell/60">{t("habits.kpi.good")}</p>
                <p className="mt-1 text-3xl font-semibold text-emerald-300">{good}<span className="text-lg text-shell/60"> / {n}</span></p>
                <p className="mt-0.5 text-xs text-shell/60">≥ {percent(GOOD_DAY)} %</p>
              </div>
              <div className={CARD}>
                <p className="text-xs uppercase tracking-[0.15em] text-shell/60">{t("habits.kpi.streak")}</p>
                <p className="mt-1 text-3xl font-semibold text-orbit">{t("habits.kpi.days", { n: bestRun(days) })}</p>
                <p className="mt-0.5 text-xs text-shell/60">{t("habits.badge.streak3")} / {t("habits.badge.streak7")}</p>
              </div>
              <div className={CARD}>
                <p className="text-xs uppercase tracking-[0.15em] text-shell/60">{t("habits.kpi.best")}</p>
                <p className="mt-1 text-3xl font-semibold text-shell">{best ? percent(best.score) : 0}<span className="text-lg"> %</span></p>
                <p className="mt-0.5 text-xs text-shell/60">{best ? `${weekday(best.date)} ${short(best.key)}` : ""}</p>
              </div>
            </div>

            <div className={`${CARD} mt-3`}>
              <p className="text-xs text-shell/70">{t("habits.scoreChart", { good: percent(GOOD_DAY) })}</p>
              <div className="mt-2 flex gap-2">
                <div aria-hidden className="flex h-36 flex-col justify-between text-xs text-shell/60"><span>100</span><span>50</span><span>0</span></div>
                <div data-habits-score-chart className="relative flex h-36 flex-1 items-end gap-px border-b border-shell/20">
                  <div aria-hidden className="absolute inset-x-0 top-1/2 border-t border-dashed border-shell/10" />
                  <div aria-hidden className="absolute inset-x-0 border-t border-dashed border-pulse/60" style={{ bottom: `${GOOD_DAY * 100}%` }} />
                  {days.map((day) => (
                    <div key={day.key} className="group flex h-full flex-1 flex-col justify-end" title={`${weekday(day.date)} ${short(day.key)}: ${percent(day.score)} %`}>
                      <div className={`w-full ${tone(day.score)} opacity-90 group-hover:opacity-100`} style={{ height: `${Math.max(day.score * 100, 2)}%` }} />
                    </div>
                  ))}
                </div>
              </div>
              <p className="mt-1 flex justify-between pl-7 text-xs text-shell/60"><span>{short(days[0].key)}</span><span>{short(days[Math.floor(n / 2)].key)}</span><span>{short(days[n - 1].key)}</span></p>
            </div>

            <div className="mt-3 grid gap-3 md:grid-cols-[1.4fr_1fr]">
              <div className={CARD}>
                <h3 className="text-xs uppercase tracking-[0.15em] text-orbit">{t("habits.perHabit")}</h3>
                <ul className="mt-2 space-y-3">
                  {HABITS.map((habit) => {
                    const stats = habitStats(days, habit);
                    const top = Math.max(habit.target, ...days.map((day) => day.values[habit.id] ?? 0));
                    return (
                      <li key={habit.id} data-habit-card={habit.id}>
                        <div className="flex items-baseline justify-between">
                          <span className="font-medium">{t(habit.title)}</span>
                          <span className="text-xs text-shell/60">{t("habits.card.reached", { reached: stats.reached, days: n })}</span>
                        </div>
                        <div className="mt-1 flex h-8 items-end gap-px">
                          {days.map((day) => {
                            const value = day.values[habit.id] ?? 0;
                            return <div key={day.key} title={`${short(day.key)}: ${value}`} className={`flex-1 ${value >= habit.target ? "bg-emerald-400/90" : value > 0 ? "bg-amber-400/80" : "bg-shell/10"}`} style={{ height: `${Math.max((value / top) * 100, 4)}%` }} />;
                          })}
                        </div>
                        <p className="mt-0.5 text-xs text-shell/60">{t("habits.card.average", { average: Math.round(stats.average * 10) / 10, unit: t(habit.unit), target: habit.target })}</p>
                      </li>
                    );
                  })}
                </ul>
              </div>

              <div className={CARD}>
                <h3 className="text-xs uppercase tracking-[0.15em] text-orbit">{t("habits.weekday.title")}</h3>
                <div className="mt-2 flex h-28 items-end gap-1.5">
                  {byWeekday.map((day) => (
                    <div key={day.name} className="flex h-full flex-1 flex-col justify-end text-center">
                      <div className={`w-full ${day.score === null ? "bg-shell/10" : tone(day.score)}`} style={{ height: `${Math.max((day.score ?? 0) * 100, 3)}%` }} title={day.score === null ? "" : `${percent(day.score)} %`} />
                    </div>
                  ))}
                </div>
                <div className="mt-1 flex gap-1.5 text-center text-xs text-shell/60">{byWeekday.map((day) => <span key={day.name} className="flex-1">{day.name}</span>)}</div>
                {bestWeekday && worstWeekday && <p className="mt-3 text-xs text-shell/70">{t("habits.weekday.insight", { best: bestWeekday.name, worst: worstWeekday.name })}</p>}
              </div>
            </div>
          </>
        )}
        </div>
      </section>
    </div>
  );
}

/**
 * Daily habits as a game: a bar per habit with a "+" to log it, a 7-day histogram of the selected one, XP, level,
 * streak and badges. A reminder appears for every habit whose hour has passed and whose target is not reached.
 */
export function HabitsPanel({ sleepHours }: { /** Hours slept, as typed in "Registrar medidas"; it fills the sleep habit of today. */ sleepHours?: number | null }) {
  const t = useT();
  const log = useHabitLog();
  const [selected, setSelected] = useState<HabitId>("exercise");
  const [span, setSpan] = useState(7);
  const [expanded, setExpanded] = useState(false);
  const [folded, setFolded] = useState(true);
  // PULSAR was asked to log a habit or to show them: the panel opens so the change is seen.
  useHudAction((action) => {
    if (action.type === "log_habit") {
      const habit = HABITS.find((item) => item.id === action.habit);
      if (!habit || habit.fromReport || !(action.amount > 0)) return;
      logHabit(habit.id, action.amount);
      setFolded(false);
    } else if (action.type === "close_panels") {
      setFolded(true);
      setExpanded(false);
    } else if (action.type === "open_habits") {
      setFolded(false);
      if (action.expand) setExpanded(true);
    }
  });
  useEffect(() => {
    if (sleepHours != null) setHabit("sleep", sleepHours);
  }, [sleepHours]);
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
  const score = percent(dayScore(log, dayKey(today)));

  return (
    <HudPanel data-habits title={<span className={due.length ? "animate-pulse text-amber-300" : ""}>{t("habits.title")}{due.length ? ` · ${due.length}` : ""}</span>} open={!folded} onOpenChange={(open) => setFolded(!open)}>
      <p className="flex justify-between text-shell">
        <span>{t("habits.level", { level: levelOf(xp) })}</span>
        <span>{t("habits.streak", { days })}</span>
      </p>
      <div className="mt-1 h-1.5 bg-shell/15">
        <div className="h-full bg-pulse" style={{ width: `${((xp % XP_PER_LEVEL) / XP_PER_LEVEL) * 100}%` }} />
      </div>
      <p className="mt-0.5 text-xs text-shell/60">{t("habits.xp", { xp: xp % XP_PER_LEVEL, next: XP_PER_LEVEL })}</p>

      <p data-habit-score className={`mt-2 ${score >= 100 ? "text-emerald-300" : "text-shell"}`}>
        {score >= 100 ? t("habits.perfect") : t("habits.today", { score })}
      </p>

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
              {habit.fromReport ? (
                <span title={t("habits.sleepFromReport")} className="w-5 text-center text-xs text-shell/60">⌂</span>
              ) : (
                <button
                  type="button"
                  data-habit-add={habit.id}
                  aria-label={t("habits.add", { habit: t(habit.title) })}
                  onClick={() => logHabit(habit.id, habit.step)}
                  className="pointer-events-auto border border-pulse/50 px-1.5 text-pulse hover:bg-pulse/20"
                >
                  +
                </button>
              )}
            </li>
          );
        })}
      </ul>

      <div className="mt-2 flex items-center gap-1">
        {[3, 7, 30].map((n) => (
          <button key={n} type="button" data-habit-range={n} aria-pressed={span === n} onClick={() => setSpan(n)} className={`pointer-events-auto border px-1.5 py-0.5 ${span === n ? "border-pulse text-pulse" : "border-shell/30 text-shell/60"}`}>
            {t(`habits.range.${n}` as Key)}
          </button>
        ))}
        <button type="button" data-habit-expand onClick={() => setExpanded(true)} className="pointer-events-auto ml-auto border border-pulse/50 px-1.5 py-0.5 text-pulse hover:bg-pulse/20">{t("habits.expand")}</button>
      </div>
      <Histogram id={selected} log={log} n={span} />
      <p className="mt-0.5 text-xs text-shell/60">{t("habits.histogram", { habit: t(HABITS.find((item) => item.id === selected)!.title), days: span })}</p>
      {/* A portal: the panel's backdrop blur would otherwise make it the frame of the dialog. */}
      {expanded && createPortal(<Expanded log={log} today={today} onClose={() => setExpanded(false)} />, document.body)}

      <p className="mt-2 flex flex-wrap gap-1">
        {BADGES.map((badge) => (
          <span key={badge.id} data-badge={badge.id} className={`border px-1.5 py-0.5 ${badge.earned(log, days) ? "border-emerald-400 text-emerald-300" : "border-shell/20 text-shell/60"}`}>
            {t(badge.label)}
          </span>
        ))}
      </p>
      <p className="mt-2 text-xs normal-case leading-snug tracking-normal text-shell/60">{t("habits.note")}</p>
    </HudPanel>
  );
}
