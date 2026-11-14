"use client";

import { useEffect, useRef, useState, type MutableRefObject, type RefObject } from "react";
import { sendBiometrics } from "./biometricsApi";
import type { Biometrics, FaceFrame } from "./faceWorker";

const FPS = 15; // goals/G1-camera-fatigue.md asks for 15 fps or more
const POST_EVERY_MS = 1000; // how often the numbers go to the local backend
const SHOW_EVERY_MS = 250; // how often the HUD re-renders with new numbers; the overlay reads every frame from a ref
const INPUT_WIDTH = 640; // the face model works at about 256 px: a full-HD frame only costs copying and resizing

/**
 * Runs the MediaPipe worker over the camera while it is live and hands its numbers to the backend.
 * Invisible by design: it adds no UI, only `window.__pulsarBiometrics` so a test can read the latest reading.
 */
export function useFaceMetrics(
  videoRef: RefObject<HTMLVideoElement | null>,
  live: boolean,
  frameRef?: MutableRefObject<FaceFrame | null>, // the landmarks of the last frame, for FaceOverlay
  onError?: (message: string) => void, // must be stable (a state setter): the worker restarts when it changes
) {
  const [latest, setLatest] = useState<Biometrics | null>(null);
  const posted = useRef(0);
  const shown = useRef(0);

  // The worker starts with the page and loads its models at once (about 25 MB plus the GPU set-up), so they are
  // ready by the time the camera permission is granted instead of starting to load on the first frame.
  const [worker, setWorker] = useState<Worker | null>(null);
  useEffect(() => {
    const w = new Worker(new URL("./faceWorker.ts", import.meta.url));
    w.postMessage({ type: "warm" });
    setWorker(w);
    return () => w.terminate();
  }, []);

  useEffect(() => {
    if (!live || !worker) return;
    let on = true;
    let timer = 0;
    worker.onerror = () => onError?.("el proceso de cara se detuvo");

    worker.onmessage =(event: MessageEvent<{ type: string; biometrics?: Biometrics; frame?: FaceFrame; message?: string }>) => {
      // Typically the model files are missing (they are not in git: `make prefetch` downloads them). Say so
      // instead of leaving the mesh and the camera readings silently absent.
      if (on && event.data.type === "error") onError?.(event.data.message ?? "no se pudieron cargar los modelos de cara");
      if (on && event.data.type === "face" && event.data.frame && frameRef) frameRef.current = event.data.frame;
      if (!on || event.data.type !== "biometrics" || !event.data.biometrics) return;
      const reading = event.data.biometrics;
      (window as unknown as { __pulsarBiometrics?: Biometrics }).__pulsarBiometrics = reading;
      const now = Date.now();
      if (now - shown.current >= SHOW_EVERY_MS) {
        shown.current = now;
        setLatest(reading); // re-renders the whole HUD (mascot included): four times a second, not every frame
      }
      if (now - posted.current >= POST_EVERY_MS) {
        posted.current = now;
        sendBiometrics(reading).catch(() => undefined); // the backend may be down; the HUD keeps working
      }
    };

    const pump = async () => {
      const video = videoRef.current;
      if (!on) return;
      const started = performance.now();
      if (video?.videoWidth) {
        try {
          const bitmap = await createImageBitmap(video, {
            resizeWidth: INPUT_WIDTH,
            resizeHeight: Math.round((INPUT_WIDTH * video.videoHeight) / video.videoWidth),
            resizeQuality: "low",
          });
          worker.postMessage({ type: "frame", bitmap, at: Math.round(performance.now()) }, [bitmap]);
        } catch {
          // a frame that cannot be read is simply skipped
        }
      }
      // Copying the frame takes time too: wait only for what is left of this frame's slot, so FPS is really FPS.
      if (on) timer = window.setTimeout(pump, Math.max(0, 1000 / FPS - (performance.now() - started)));
    };
    void pump();

    return () => {
      on = false;
      clearTimeout(timer);
      worker.onmessage = null;
      worker.postMessage({ type: "stop" });
      if (frameRef) frameRef.current = null;
      setLatest(null); // the camera is gone: do not leave its last reading up as if it were current
    };
  }, [live, worker, videoRef, frameRef, onError]);

  return latest;
}
