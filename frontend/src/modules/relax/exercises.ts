import type { Key } from "@/i18n";

/**
 * Relaxation exercises PULSAR offers. They are generic, widely taught techniques (slow breathing, resting the eyes,
 * releasing tension): the timings are team assumptions, not NASA figures, and none of this is medical advice. What NASA's
 * sleep-risk narrative contributes is the reason to offer them: stress, noise, light and schedule shifts drive sleep
 * loss and fatigue (https://www.nasa.gov/wp-content/uploads/2025/09/sleep-risk-dag-narrative-sa-07566.pdf).
 */
export type Phase = {
  /** Message key of what to do during this phase. */
  key: Key;
  seconds: number;
  /** How big the guide circle is at the end of the phase (0.4 small, 1 large). */
  scale: number;
};

export type Exercise = {
  id: "breathe" | "eyes" | "body";
  title: Key;
  hint: Key;
  /** The phases in order, repeated `rounds` times. */
  phases: Phase[];
  rounds: number;
};

export const EXERCISES: Exercise[] = [
  {
    id: "breathe",
    title: "relax.breathe.title",
    hint: "relax.breathe.hint",
    phases: [
      { key: "relax.breathe.in", seconds: 4, scale: 1 },
      { key: "relax.breathe.hold", seconds: 2, scale: 1 },
      { key: "relax.breathe.out", seconds: 6, scale: 0.4 },
    ],
    rounds: 5,
  },
  {
    id: "eyes",
    title: "relax.eyes.title",
    hint: "relax.eyes.hint",
    phases: [
      { key: "relax.eyes.far", seconds: 20, scale: 1 },
      { key: "relax.eyes.blink", seconds: 8, scale: 0.7 },
      { key: "relax.eyes.close", seconds: 10, scale: 0.4 },
    ],
    rounds: 1,
  },
  {
    id: "body",
    title: "relax.body.title",
    hint: "relax.body.hint",
    phases: [
      { key: "relax.body.shoulders", seconds: 10, scale: 0.55 },
      { key: "relax.body.jaw", seconds: 10, scale: 0.7 },
      { key: "relax.body.hands", seconds: 10, scale: 0.85 },
      { key: "relax.body.breath", seconds: 10, scale: 0.4 },
    ],
    rounds: 2,
  },
];

export const totalSeconds = (exercise: Exercise) => exercise.rounds * exercise.phases.reduce((sum, phase) => sum + phase.seconds, 0);

/** Where `elapsed` seconds into an exercise falls: the phase, the time left in it and whether it is over. */
export function position(exercise: Exercise, elapsed: number) {
  const round = exercise.phases.reduce((sum, phase) => sum + phase.seconds, 0);
  if (elapsed >= totalSeconds(exercise)) return { done: true as const };
  let inRound = elapsed % round;
  for (const phase of exercise.phases) {
    if (inRound < phase.seconds) return { done: false as const, phase, left: Math.ceil(phase.seconds - inRound) };
    inRound -= phase.seconds;
  }
  return { done: true as const };
}
