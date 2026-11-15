import { describe, expect, it } from "vitest";
import { dayKey, daysBack, dayScore, history, levelOf, pending, streak, totalXp, type Log } from "./habits";

const today = new Date(2026, 10, 15, 19, 0); // 15 Nov 2026, 19:00
const perfect = { sleep: 8.5, exercise: 120, water: 8, relax: 3 };

describe("habits", () => {
  it("scores a day by the average progress, capped at the target", () => {
    const log: Log = { "2026-11-15": { sleep: 17, exercise: 60 } };
    expect(dayScore(log, "2026-11-15")).toBeCloseTo((1 + 0.5) / 4);
  });

  it("counts the streak of good days and does not break it while today is in progress", () => {
    const log: Log = { [dayKey(daysBack(today, 1))]: perfect, [dayKey(daysBack(today, 2))]: perfect };
    expect(streak(log, today)).toBe(2);
    log[dayKey(today)] = perfect;
    expect(streak(log, today)).toBe(3);
    expect(streak({ [dayKey(daysBack(today, 2))]: perfect }, today)).toBe(0);
  });

  it("gives 100 xp per perfect day and a level every 300", () => {
    const log: Log = { a: perfect, b: perfect, c: perfect };
    expect(totalXp(log)).toBe(300);
    expect(levelOf(300)).toBe(2);
  });

  it("reminds of what is due and not reached yet", () => {
    const log: Log = { [dayKey(today)]: { sleep: 8.5, exercise: 120 } };
    expect(pending(log, today).map((habit) => habit.id)).toEqual(["relax"]); // water is due from 20:00
  });

  it("lists seven days, oldest first", () => {
    const days = history({}, "water", today);
    expect(days).toHaveLength(7);
    expect(days[6].key).toBe("2026-11-15");
  });
});
