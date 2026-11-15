import type { Key } from "@/i18n";

/**
 * Daily habits of an astronaut that PULSAR tracks. The targets are TEAM ASSUMPTIONS taken from what is commonly
 * reported about the ISS crew day (about 8.5 h of scheduled sleep and about 2 h of exercise to limit bone and muscle
 * loss), not figures from a NASA document we could cite: the reasons come from the HRP risks "Reduced Cardiorespiratory
 * and Musculoskeletal Fitness" and "Risk of Performance Decrements ... from Sleep Loss" (shared/sources.json).
 * Hydration and relaxation targets are our own wording. None of this is medical advice.
 */
export type HabitId = "sleep" | "exercise" | "water" | "relax";

export type Habit = {
  id: HabitId;
  title: Key;
  unit: Key;
  target: number;
  /** What one tap on "+" adds. */
  step: number;
  /** Local hour from which a reminder is shown while the target is not reached. */
  dueHour: number;
  /** Typed in "Registrar medidas", not here: the panel shows it and offers no "+". */
  fromReport?: boolean;
};

export const HABITS: Habit[] = [
  { id: "sleep", title: "habits.sleep", unit: "habits.unit.h", target: 8.5, step: 0.5, dueHour: 10, fromReport: true },
  { id: "exercise", title: "habits.exercise", unit: "habits.unit.min", target: 120, step: 30, dueHour: 18 },
  { id: "water", title: "habits.water", unit: "habits.unit.glasses", target: 8, step: 1, dueHour: 20 },
  { id: "relax", title: "habits.relax", unit: "habits.unit.times", target: 3, step: 1, dueHour: 17 },
];

/** Values per local day (YYYY-MM-DD), per habit. */
export type Log = Record<string, Partial<Record<HabitId, number>>>;

const pad = (n: number) => String(n).padStart(2, "0");
export const dayKey = (date: Date) => `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
export const daysBack = (from: Date, n: number) => new Date(from.getFullYear(), from.getMonth(), from.getDate() - n);

/** How much of a habit's target a day reached, from 0 to 1. */
export const progress = (habit: Habit, value = 0) => Math.min(value / habit.target, 1);

/** The average progress of all habits on one day, from 0 to 1. */
export const dayScore = (log: Log, key: string) =>
  HABITS.reduce((sum, habit) => sum + progress(habit, log[key]?.[habit.id]), 0) / HABITS.length;

export const GOOD_DAY = 0.8;
const XP_PER_DAY = 100;
export const XP_PER_LEVEL = 300;

export const totalXp = (log: Log) => Math.round(Object.keys(log).reduce((sum, key) => sum + dayScore(log, key) * XP_PER_DAY, 0));
export const levelOf = (xp: number) => Math.floor(xp / XP_PER_LEVEL) + 1;

/** Consecutive good days up to today; a day that is still in progress does not break the streak. */
export function streak(log: Log, today: Date): number {
  let count = 0;
  for (let back = 0; back < 3650; back++) {
    const good = dayScore(log, dayKey(daysBack(today, back))) >= GOOD_DAY;
    if (good) count++;
    else if (back > 0) break;
  }
  return count;
}

/** Habits whose reminder hour has passed and whose target is not reached yet. */
export const pending = (log: Log, now: Date) =>
  HABITS.filter((habit) => now.getHours() >= habit.dueHour && (log[dayKey(now)]?.[habit.id] ?? 0) < habit.target);

/** The last `n` days, oldest first, with the value of one habit. */
export const history = (log: Log, id: HabitId, today: Date, n = 7) =>
  Array.from({ length: n }, (_, i) => {
    const date = daysBack(today, n - 1 - i);
    return { key: dayKey(date), date, value: log[dayKey(date)]?.[id] ?? 0 };
  });

/**
 * DEMO DATA, not measurements: the 60 days before today, so the history, the month view and the streak are not empty on
 * a first run. A fixed pattern (a rest day every sixth day, a short night every fifth) so the charts are not flat.
 */
export function mockLog(today: Date): Log {
  const log: Log = {};
  for (let back = 1; back <= 60; back++) {
    const rest = back % 6 === 0;
    log[dayKey(daysBack(today, back))] = {
      sleep: back % 5 === 0 ? 6.5 : back % 3 === 0 ? 7.5 : 8.5,
      exercise: rest ? 0 : back % 4 === 0 ? 60 : back % 7 === 0 ? 90 : 120,
      water: rest ? 5 : back % 4 === 0 ? 6 : 8,
      relax: rest ? 1 : back % 4 === 0 ? 2 : 3,
    };
  }
  return log;
}

/** Every day from `from` to `to` (both included, oldest first) with its score and the value of each habit. */
export function range(log: Log, from: Date, to: Date) {
  const days: { key: string; date: Date; score: number; values: Partial<Record<HabitId, number>> }[] = [];
  for (let date = from; date <= to && days.length < 366; date = daysBack(date, -1)) {
    const key = dayKey(date);
    days.push({ key, date, score: dayScore(log, key), values: log[key] ?? {} });
  }
  return days;
}

/** What a range says about one habit: its average per day and on how many days the target was reached. */
export const habitStats = (days: ReturnType<typeof range>, habit: Habit) => ({
  average: days.length ? days.reduce((sum, day) => sum + (day.values[habit.id] ?? 0), 0) / days.length : 0,
  reached: days.filter((day) => (day.values[habit.id] ?? 0) >= habit.target).length,
});

export const BADGES = [
  { id: "perfect", label: "habits.badge.perfect", earned: (log: Log) => Object.keys(log).some((key) => dayScore(log, key) >= 1) },
  { id: "streak3", label: "habits.badge.streak3", earned: (_: Log, days: number) => days >= 3 },
  { id: "streak7", label: "habits.badge.streak7", earned: (_: Log, days: number) => days >= 7 },
] as const;
