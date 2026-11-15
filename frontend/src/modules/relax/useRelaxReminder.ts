"use client";

import { useCallback, useEffect, useRef, useState } from "react";

/** Minutes between reminders (team assumption; there is no setting for it). */
const EVERY_MIN = 30;
const SNOOZE_MIN = 5;

/**
 * Tells the astronaut to relax every half hour. `due` turns true when the time is up and stays true until the reminder
 * is answered: `snooze` asks again in 5 minutes, `done` starts the interval over. The clock waits while `paused`
 * (the exercises are open).
 */
export function useRelaxReminder(paused: boolean) {
  const [due, setDue] = useState(false);
  const nextAt = useRef(Date.now() + EVERY_MIN * 60_000);

  useEffect(() => {
    if (paused) return;
    const id = setInterval(() => {
      if (Date.now() >= nextAt.current) setDue(true);
    }, 1000);
    return () => clearInterval(id);
  }, [paused]);

  const snooze = useCallback(() => {
    setDue(false);
    nextAt.current = Date.now() + SNOOZE_MIN * 60_000;
  }, []);

  const done = useCallback(() => {
    setDue(false);
    nextAt.current = Date.now() + EVERY_MIN * 60_000;
  }, []);

  return { due, snooze, done };
}
