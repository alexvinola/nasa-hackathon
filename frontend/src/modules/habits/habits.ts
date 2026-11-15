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
};

export const HABITS: Habit[] = [
  { id: "sleep", title: "habits.sleep", unit: "habits.unit.h", target: 8.5, step: 0.5, dueHour: 10 },
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

export const BADGES = [
  { id: "perfect", label: "habits.badge.perfect", earned: (log: Log) => Object.keys(log).some((key) => dayScore(log, key) >= 1) },
  { id: "streak3", label: "habits.badge.streak3", earned: (_: Log, days: number) => days >= 3 },
  { id: "streak7", label: "habits.badge.streak7", earned: (_: Log, days: number) => days >= 7 },
] as const;
