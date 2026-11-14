"use client";

import { useEffect, useRef, useState, type MutableRefObject, type RefObject } from "react";
import { frameBase64 } from "@/modules/voice-ai/pulsarApi";
import type { FaceFrame } from "./faceWorker";

const API = process.env.NEXT_PUBLIC_PULSAR_API ?? "http://localhost:8000";
const EVERY_MS = 6000; // Gemma also directs the mascot and phrases verdicts: one check every few seconds is enough
const BLINK = 0.5; // the worker's own thresholds, so the claim is exactly what the metrics counted
const MOUTH = 0.35;

type State = "open" | "closed";
export type AiCheck = {
  claim: { eyes: State; mouth: State };
  ai: { person: boolean; eyes: State | "unclear"; mouth: State | "unclear" };
  agrees: { eyes: boolean | null; mouth: boolean | null };
  ms: number;
};
export type Tally = { agree: number; total: number };

/**
 * Every few seconds sends the current frame and MediaPipe's reading of it to POST /vision/verify, where Gemma looks
 * at the same picture. Keeps the last answer and a running agreement count per feature (unclear answers don't count).
 */
export function useAiCheck(videoRef: RefObject<HTMLVideoElement | null>, frameRef: MutableRefObject<FaceFrame | null>, on: boolean) {
  const [last, setLast] = useState<AiCheck | null>(null);
  const [tally, setTally] = useState<{ eyes: Tally; mouth: Tally }>({ eyes: { agree: 0, total: 0 }, mouth: { agree: 0, total: 0 } });
  const [error, setError] = useState<string | null>(null);
  const busy = useRef(false);

  useEffect(() => {
    if (!on) return;
    const id = setInterval(async () => {
      const frame = frameRef.current;
      if (busy.current || !frame?.face) return;
      busy.current = true;
      try {
        const claim = {
          eyes: ((frame.eyeLeft + frame.eyeRight) / 2 > BLINK ? "closed" : "open") as State,
          mouth: (frame.jaw > MOUTH ? "open" : "closed") as State,
        };
        const image = await frameBase64(videoRef.current);
        if (!image) return;
        const response = await fetch(`${API}/vision/verify`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ image, claim }),
        });
        if (!response.ok) throw new Error(`AI check: backend error ${response.status}`);
        const check: AiCheck = await response.json();
        setLast(check);
        setError(null);
        setTally((t) => ({
          eyes: check.agrees.eyes === null ? t.eyes : { agree: t.eyes.agree + Number(check.agrees.eyes), total: t.eyes.total + 1 },
          mouth: check.agrees.mouth === null ? t.mouth : { agree: t.mouth.agree + Number(check.agrees.mouth), total: t.mouth.total + 1 },
        }));
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e));
      } finally {
        busy.current = false;
      }
    }, EVERY_MS);
    return () => clearInterval(id);
  }, [on, videoRef, frameRef]);

  return { last, tally, error };
}
