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
      // 720p: the face model works at 640 px wide, so a full-HD stream only costs decoding and shrinking every frame.
      .getUserMedia({ video: { width: { ideal: 1280 }, height: { ideal: 720 }, frameRate: { ideal: 30 }, facingMode: "user" }, audio: false })
      .then(async (s) => {
        if (cancelled) return s.getTracks().forEach((t) => t.stop());
        stream = s;
        // Unplugged or revoked mid-session: stop claiming the camera is live.
        s.getVideoTracks()[0]?.addEventListener("ended", () => setState("unavailable"));
        const v = videoRef.current;
        if (v) {
          v.srcObject = s;
          await v.play(); // a rejection falls through to the catch below
        }
        if (!cancelled) setState("live");
      })
      .catch((e: DOMException) => setState(e.name === "NotAllowedError" ? "denied" : "unavailable"));
    return () => {
      cancelled = true;
      stream?.getTracks().forEach((t) => t.stop());
    };
  }, []);

  return { videoRef, state };
}
