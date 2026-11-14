"use client";

import { useEffect, useRef, useState } from "react";
import type { Biometrics } from "@/modules/vision-hud/faceWorker";
import { speak } from "./pulsarApi";
import { advise, evaluate, telemetryFrom, type Advice, type Decision } from "./verdictApi";

const EVERY_MS = 2000;

/** What made the engine decide: when this changes, PULSAR has something new to say. */
const reasonOf = (d: Decision) => `${d.status}|${d.factors.map((f) => f.signal).join(",")}`;

/**
 * Asks the rules engine every 2 s with the latest camera reading. When the status or its reasons change, it asks
 * for the spoken sentence and says it with Piper. Requests never overlap; a backend that is down leaves the last
 * verdict on screen with `error` set.
 */
export function useVerdict(biometrics: Biometrics | null) {
  const [decision, setDecision] = useState<Decision | null>(null);
  const [advice, setAdvice] = useState<Advice | null>(null);
  const [error, setError] = useState<string | null>(null);
  const latest = useRef(biometrics);
  latest.current = biometrics;
  const busy = useRef(false);
  const lastReason = useRef("");

  useEffect(() => {
    const tick = async () => {
      if (busy.current || !latest.current) return;
      busy.current = true;
      try {
        const telemetry = telemetryFrom(latest.current);
        const next = await evaluate(telemetry);
        setDecision(next);
        setError(null);
        const reason = reasonOf(next);
        if (reason !== lastReason.current) {
          lastReason.current = reason;
          const spoken = await advise(telemetry);
          setAdvice(spoken);
          speak(spoken.say).catch(() => undefined); // no voice installed: the sentence stays on screen
        }
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e));
      } finally {
        busy.current = false;
      }
    };
    const id = setInterval(tick, EVERY_MS);
    return () => clearInterval(id);
  }, []);

  return { decision, advice, error };
}
