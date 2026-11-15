import { describe, expect, it } from "vitest";
import { dayKey, daysBack, dayScore, history, levelOf, mockLog, pending, range, habitStats, HABITS, streak, totalXp, type Log } from "./habits";

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

describe("mockLog", () => {
  it("fills the 60 days before today with every habit and none of today", () => {
    const today = new Date(2026, 10, 15);
    const log = mockLog(today);
    expect(Object.keys(log)).toHaveLength(60);
    expect(log[dayKey(today)]).toBeUndefined();
    expect(history(log, "exercise", daysBack(today, 1)).every((d) => d.key in log)).toBe(true);
  });
});

describe("perfect day and ranges", () => {
  it("scores exactly 1 when every habit reaches its target, and 0 when none does", () => {
    const full = Object.fromEntries(HABITS.map((habit) => [habit.id, habit.target]));
    expect(HABITS).toHaveLength(4);
    expect(dayScore({ d: full }, "d")).toBe(1);
    expect(dayScore({}, "d")).toBe(0);
  });

  it("summarises a range: days, average and days on target", () => {
    const log = mockLog(today);
    const days = range(log, daysBack(today, 30), daysBack(today, 1));
    expect(days).toHaveLength(30);
    const exercise = HABITS.find((habit) => habit.id === "exercise")!;
    expect(habitStats(days, exercise).reached).toBeGreaterThan(0);
  });
});
