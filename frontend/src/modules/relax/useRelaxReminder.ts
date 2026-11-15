"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { REMINDER_OPTIONS, type ReminderEvery } from "./exercises";

const STORAGE = "pulsar-relax-every";
const SNOOZE_MIN = 5;

function saved(): ReminderEvery {
  try {
    const stored = localStorage.getItem(STORAGE);
    const value = Number(stored);
    return stored !== null && (REMINDER_OPTIONS as readonly number[]).includes(value) ? (value as ReminderEvery) : 30;
  } catch {
    return 30; // no storage: the default lasts until reload
  }
}

/**
 * Tells the astronaut to relax every `every` minutes (0 is off). `due` turns true when the time is up and stays true
 * until the reminder is answered: `snooze` asks again in 5 minutes, `done` starts the interval over. Nothing
 * interrupts while `paused` (an exercise is running); the clock waits.
 */
export function useRelaxReminder(paused: boolean) {
  const [every, setEveryState] = useState<ReminderEvery>(30);
  const [due, setDue] = useState(false);
  const nextAt = useRef(0);

  // The saved choice is read after hydration, so the server and the first client render agree.
  useEffect(() => {
    const value = saved();
    setEveryState(value);
    nextAt.current = Date.now() + value * 60_000;
  }, []);

  useEffect(() => {
    if (!every || paused) return;
    const id = setInterval(() => {
      if (Date.now() >= nextAt.current) setDue(true);
    }, 1000);
    return () => clearInterval(id);
  }, [every, paused]);

  const setEvery = useCallback((value: ReminderEvery) => {
    setEveryState(value);
    setDue(false);
    nextAt.current = Date.now() + value * 60_000;
    try {
      localStorage.setItem(STORAGE, String(value));
    } catch {
      // private window: the choice just lasts until reload
    }
  }, []);

  const snooze = useCallback(() => {
    setDue(false);
    nextAt.current = Date.now() + SNOOZE_MIN * 60_000;
  }, []);

  const done = useCallback(() => {
    setDue(false);
    nextAt.current = Date.now() + every * 60_000;
  }, [every]);

  return { every, setEvery, due: due && every > 0, snooze, done };
}
