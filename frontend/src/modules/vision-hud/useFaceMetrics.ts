"use client";

import { useEffect, useRef, useState, type RefObject } from "react";
import { sendBiometrics } from "./biometricsApi";
import type { Biometrics } from "./faceWorker";

const FPS = 15; // goals/G1-camera-fatigue.md asks for 15 fps or more
const POST_EVERY_MS = 1000; // how often the numbers go to the local backend

/**
 * Runs the MediaPipe worker over the camera while it is live and hands its numbers to the backend.
 * Invisible by design: it adds no UI, only `window.__pulsarBiometrics` so a test can read the latest reading.
 */
export function useFaceMetrics(videoRef: RefObject<HTMLVideoElement | null>, live: boolean) {
  const [latest, setLatest] = useState<Biometrics | null>(null);
  const posted = useRef(0);

  useEffect(() => {
    if (!live) return;
    const worker = new Worker(new URL("./faceWorker.ts", import.meta.url));
    let on = true;
    let timer = 0;

    worker.onmessage = (event: MessageEvent<{ type: string; biometrics?: Biometrics }>) => {
      if (!on || event.data.type !== "biometrics" || !event.data.biometrics) return;
      const reading = event.data.biometrics;
      setLatest(reading);
      (window as unknown as { __pulsarBiometrics?: Biometrics }).__pulsarBiometrics = reading;
      const now = Date.now();
      if (now - posted.current >= POST_EVERY_MS) {
        posted.current = now;
        sendBiometrics(reading).catch(() => undefined); // the backend may be down; the HUD keeps working
      }
    };

    const pump = async () => {
      const video = videoRef.current;
      if (!on) return;
      if (video?.videoWidth) {
        try {
          const bitmap = await createImageBitmap(video);
          worker.postMessage({ type: "frame", bitmap, at: Math.round(performance.now()) }, [bitmap]);
        } catch {
          // a frame that cannot be read is simply skipped
        }
      }
      if (on) timer = window.setTimeout(pump, 1000 / FPS);
    };
    void pump();

    return () => {
      on = false;
      clearTimeout(timer);
      worker.postMessage({ type: "stop" });
      worker.terminate();
    };
  }, [live, videoRef]);

  return latest;
}
