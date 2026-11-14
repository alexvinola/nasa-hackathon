"use client";

import { useEffect, useRef, useState } from "react";
import { motion, useReducedMotion } from "framer-motion";
import { PulsarMascot } from "./PulsarMascot";
import type { Mood } from "./PulsarSprite3D";
import { useWebcam, type CamState } from "./useWebcam";

// shortcut: canned lines so the mascot can be reviewed, replace with the rules-engine verdict once it is wired in.
// `at` is where PULSAR flies to, as a fraction of the free screen; [0, 0] is its home corner.
const MOCK_SCRIPT: { text: string; mood: Mood; at: [number, number] }[] = [
  { text: "Hi, I'm PULSAR. I'm watching over you.", mood: "idle", at: [0, 0] },
  { text: "Taking a quick look around the cabin.", mood: "idle", at: [1, 0.15] },
  { text: "Hold still, calibrating the camera.", mood: "idle", at: [0.5, 1] },
  { text: "You look tired. How about a short break?", mood: "alert", at: [0.1, 0.6] },
  { text: "Back to my corner. Call me if you need me.", mood: "idle", at: [0, 0] },
];
// Mascot plus speech bubble plus both screen margins, so it never flies off screen.
const MASCOT_W = 192 + 12 + 260 + 64;
const MASCOT_H = 192 + 64;

const CAM_LABEL: Record<CamState, string> = {
  starting: "CAM · STARTING",
  live: "CAM · LIVE",
  denied: "CAM · PERMISSION DENIED",
  unavailable: "CAM · NOT AVAILABLE",
};

function Corner({ className }: { className: string }) {
  return <span className={`absolute h-8 w-8 border-pulse/80 ${className}`} />;
}

/** Full-screen camera with the HUD layered on top. Placeholder readouts until the verticals plug in. */
export function Hud() {
  const { videoRef, state } = useWebcam();
  const still = useReducedMotion();
  const [step, setStep] = useState(0);
  const [pos, setPos] = useState({ x: 0, y: 0 });
  const [heading, setHeading] = useState(0);
  // Last x, and the yaw that currently means "facing the camera" (grows by 2π on every spin).
  const face = useRef({ x: 0, front: 0 });
  const line = MOCK_SCRIPT[step];

  useEffect(() => {
    const id = setInterval(() => setStep((s) => (s + 1) % MOCK_SCRIPT.length), 7000);
    return () => clearInterval(id);
  }, []);

  useEffect(() => {
    const [fx, fy] = still ? [0, 0] : MOCK_SCRIPT[step].at;
    const next = { x: fx * Math.max(0, innerWidth - MASCOT_W), y: fy * Math.max(0, innerHeight - MASCOT_H) };
    setHeading(face.current.front + Math.sign(next.x - face.current.x) * 0.9); // look where it flies
    face.current.x = next.x;
    setPos(next);
  }, [step, still]);

  return (
    <main className="relative h-screen w-screen overflow-hidden bg-space">
      <video ref={videoRef} muted playsInline className="absolute inset-0 h-full w-full -scale-x-100 object-cover" />
      {state !== "live" && (
        <div className="absolute inset-0 grid place-items-center bg-[radial-gradient(ellipse_at_center,var(--color-space-lift),var(--color-space))] text-sm tracking-widest text-orbit">
          {CAM_LABEL[state]}
        </div>
      )}

      <div className="hud-scanlines pointer-events-none absolute inset-0" />
      <div className="hud-vignette pointer-events-none absolute inset-0" />

      <div className="pointer-events-none absolute inset-4">
        <Corner className="left-0 top-0 border-l-2 border-t-2" />
        <Corner className="right-0 top-0 border-r-2 border-t-2" />
        <Corner className="bottom-0 left-0 border-b-2 border-l-2" />
        <Corner className="bottom-0 right-0 border-b-2 border-r-2" />
      </div>

      <motion.div
        className="absolute left-8 top-8"
        animate={pos}
        transition={{ duration: 2.4, ease: "easeInOut" }}
        onAnimationComplete={() => {
          if (!pos.x && !pos.y) face.current.front += 2 * Math.PI; // home again: one full spin
          setHeading(face.current.front);
        }}
      >
        <PulsarMascot message={line.text} mood={line.mood} heading={heading} mock />
      </motion.div>

      <div className="absolute right-8 top-8 text-right text-[11px] tracking-[0.2em] text-pulse">
        <div className={state === "live" ? "" : "text-orbit"}>● {CAM_LABEL[state]}</div>
        <div className="mt-1 text-shell/70">OFFLINE · LOCAL ONLY</div>
      </div>

      <div className="absolute inset-x-8 bottom-8 flex items-end justify-between text-[11px] tracking-[0.2em] text-shell/70">
        <span>PULSAR HUD · v0.1</span>
        <span className="text-orbit">NOT A MEDICAL DEVICE</span>
      </div>
    </main>
  );
}
