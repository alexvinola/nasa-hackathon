"use client";

import { useEffect, useRef, useState } from "react";

export type CamState = "starting" | "live" | "denied" | "unavailable";

/** Opens the webcam (localhost only, nothing leaves the machine) and attaches it to a <video>. */
export function useWebcam() {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [state, setState] = useState<CamState>("starting");

  useEffect(() => {
    let stream: MediaStream | undefined;
    let cancelled = false;
    if (!navigator.mediaDevices?.getUserMedia) {
      setState("unavailable");
      return;
    }
    navigator.mediaDevices
      .getUserMedia({ video: { width: { ideal: 1920 }, height: { ideal: 1080 }, facingMode: "user" }, audio: false })
      .then((s) => {
        if (cancelled) return s.getTracks().forEach((t) => t.stop());
        stream = s;
        const v = videoRef.current;
        if (v) {
          v.srcObject = s;
          void v.play();
        }
        setState("live");
      })
      .catch((e: DOMException) => setState(e.name === "NotAllowedError" ? "denied" : "unavailable"));
    return () => {
      cancelled = true;
      stream?.getTracks().forEach((t) => t.stop());
    };
  }, []);

  return { videoRef, state };
}
