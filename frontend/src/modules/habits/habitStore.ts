"use client";

import { useSyncExternalStore } from "react";
import { dayKey, dayScore, HABITS, mockLog, type HabitId, type Log } from "./habits";

const KEY = "pulsar-habits-v2"; // v2: a fresh 60-day demo history and an empty today
const EMPTY: Log = {};
let log: Log | null = null;
const listeners = new Set<() => void>();

function load(): Log {
  if (log) return log;
  try {
    const saved = localStorage.getItem(KEY);
    const mine = saved ? (JSON.parse(saved) as Log) : {};
    // Demo data for the last 7 days until the astronaut has any past day of their own; their entries win.
    log = Object.keys(mine).some((key) => key !== dayKey(new Date())) ? mine : { ...mockLog(new Date()), ...mine };
  } catch {
    log = mockLog(new Date()); // private window or corrupt value
  }
  return log;
}

/** Sets a habit of today to `value` (what "Registrar medidas" typed), without adding to it. */
export function setHabit(id: HabitId, value: number, now = new Date()) {
  const day = dayKey(now);
  const current = load();
  if (current[day]?.[id] === value) return;
  log = { ...current, [day]: { ...current[day], [id]: value } };
  try {
    localStorage.setItem(KEY, JSON.stringify(log));
  } catch {
    /* kept in memory */
  }
  listeners.forEach((listener) => listener());
}

/** Adds `amount` to a habit of today (never below 0) and tells every panel listening. */
export function logHabit(id: HabitId, amount: number, now = new Date()) {
  const habit = HABITS.find((item) => item.id === id);
  if (!habit) return;
  const day = dayKey(now);
  const current = load();
  const value = Math.max(0, Math.round(((current[day]?.[id] ?? 0) + amount) * 100) / 100);
  log = { ...current, [day]: { ...current[day], [id]: value } };
  try {
    localStorage.setItem(KEY, JSON.stringify(log));
  } catch {
    /* the habit stays in memory for this session */
  }
  listeners.forEach((listener) => listener());
}

/** Today's habits as PULSAR needs them to answer "how am I doing": the score (0 to 1) and each habit's value. */
export function todayHabits(now = new Date()): Record<string, number> {
  const current = load();
  const key = dayKey(now);
  return { score: dayScore(current, key), ...Object.fromEntries(HABITS.map((habit) => [habit.id, current[key]?.[habit.id] ?? 0])) };
}

export function useHabitLog(): Log {
  return useSyncExternalStore(
    (listener) => {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
    load,
    () => EMPTY,
  );
}
