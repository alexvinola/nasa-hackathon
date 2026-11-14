// The alarm's reaction check: a 10-stimulus take on the PVT-B (shared/sources.json `basner-2011-pvtb`). It is not
// the 3-minute test of goal G3, so it writes nothing to the contract and only gates stopping the alarm.
// shortcut: timings are not calibrated against display and input latency, measure them before quoting a reaction time.
export const FOREPERIOD_MS = [1000, 4000] as const; // source basner-2011-pvtb: 1-4 s between stimuli
export const LAPSE_MS = 355; // source basner-2011-pvtb: a reaction this slow is a lapse
export const FALSE_START_MS = 100; // assumption: the usual PVT convention, anything faster is a guess
export const NO_RESPONSE_MS = 2000; // assumption: the stimulus gives up after this long
export const TRIALS = 10; // assumption: short enough to take during an alarm
export const PASS_RATIO = 0.9; // assumption (team decision): 90 % of the reactions must be good

/** One stimulus: the reaction time in ms, or null for a false start or no response. */
export type Reaction = number | null;

export const isGood = (ms: Reaction) => ms !== null && ms >= FALSE_START_MS && ms < LAPSE_MS;

export function score(reactions: Reaction[]) {
  const good = reactions.filter(isGood) as number[];
  return {
    good: good.length,
    meanMs: good.length ? Math.round(good.reduce((a, b) => a + b, 0) / good.length) : null,
    passed: reactions.length >= TRIALS && good.length / reactions.length >= PASS_RATIO,
  };
}
