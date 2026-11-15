"use client";

import { useEffect, useRef, useState } from "react";
import { useLang } from "@/i18n";
import type { Biometrics } from "@/modules/vision-hud/faceWorker";
import type { Entries } from "@/modules/guides/selfReport";
import { advise, evaluate, telemetryFrom, type Advice, type Decision } from "./verdictApi";

const EVERY_MS = 2000;

/** What made the engine decide: when this changes, PULSAR has something new to say. */
const reasonOf = (d: Decision) => `${d.status}|${d.factors.map((f) => f.signal).join(",")}`;

/**
 * Asks the rules engine every 2 s with the latest reading (camera or simulated). When the status or its reasons
 * change, it asks Gemma for the sentence that phrases the new verdict and returns it as `advice`. Requests never
 * overlap; a backend that is down leaves the last verdict on screen with `error` set.
 */
export function useVerdict(biometrics: Biometrics | null, cabinCo2?: number, radiation?: number, entries: Entries = {}) {
  const typed = useRef(entries);
  typed.current = entries;
  const co2 = useRef(cabinCo2);
  co2.current = cabinCo2;
  const dose = useRef(radiation);
  dose.current = radiation;
  const lang = useLang();
  const [decision, setDecision] = useState<Decision | null>(null);
  const [advice, setAdvice] = useState<Advice | null>(null);
  const [error, setError] = useState<string | null>(null);
  const latest = useRef(biometrics);
  latest.current = biometrics;
  const busy = useRef(false);
  const advising = useRef(false);
  const lastReason = useRef("");
  const reasonNow = useRef("");

  useEffect(() => {
    const tick = async () => {
      if (busy.current || !latest.current) return;
      busy.current = true;
      try {
        const telemetry = telemetryFrom(latest.current, co2.current, dose.current, typed.current);
        const next = await evaluate(telemetry);
        setDecision(next);
        setError(null);
        const reason = (reasonNow.current = `${reasonOf(next)}|${lang}`); // a new language needs a new sentence
        // Gemma takes seconds to phrase a verdict. That must not hold up the next evaluation: an alarm has to
        // start, and stop, as soon as the engine says so. A sentence for a verdict that has since changed is dropped.
        if (reason !== lastReason.current && !advising.current) {
          lastReason.current = reason;
          advising.current = true;
          advise(telemetry)
            .then((spoken) => `${reasonOf(spoken.decision)}|${lang}` === reasonNow.current && setAdvice(spoken))
            .catch((e) => setError(e instanceof Error ? e.message : String(e)))
            .finally(() => (advising.current = false));
        }
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e));
      } finally {
        busy.current = false;
      }
    };
    const id = setInterval(tick, EVERY_MS);
    return () => clearInterval(id);
  }, [lang]);

  return { decision, advice, error };
}
