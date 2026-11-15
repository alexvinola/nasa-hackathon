"use client";

import { useSyncExternalStore } from "react";
import { dayKey, HABITS, type HabitId, type Log } from "./habits";

const KEY = "pulsar-habits";
const EMPTY: Log = {};
let log: Log | null = null;
const listeners = new Set<() => void>();

function load(): Log {
  if (log) return log;
  try {
    log = JSON.parse(localStorage.getItem(KEY) ?? "{}") as Log;
  } catch {
    log = {}; // private window or corrupt value: start empty
  }
  return log;
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
