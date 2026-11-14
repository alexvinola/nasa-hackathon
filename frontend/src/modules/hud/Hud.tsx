"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { motion, useReducedMotion } from "framer-motion";
import { PulsarMascot } from "./PulsarMascot";
import type { Mood } from "./PulsarSprite3D";
import { useWebcam, type CamState } from "./useWebcam";
import { SensesBar } from "@/modules/voice-ai/SensesBar";
import { VerdictPanel } from "@/modules/voice-ai/VerdictPanel";
import { useFaceMetrics } from "@/modules/vision-hud/useFaceMetrics";
import { FaceOverlay } from "@/modules/vision-hud/FaceOverlay";
import type { FaceFrame } from "@/modules/vision-hud/faceWorker";
import { direct, frameBase64, type Direction, type Spot } from "@/modules/voice-ai/pulsarApi";

// shortcut: canned lines so the mascot can be reviewed, replace with the rules-engine verdict once it is wired in.
// `at` is where PULSAR flies to, as a fraction of the free screen; [0, 0] is its home corner.
const MOCK_SCRIPT: { text: string; mood: Mood; at: [number, number] }[] = [
  { text: "Hi, I'm PULSAR. I'm watching over you.", mood: "idle", at: [0, 0] },
  { text: "Taking a quick look around the cabin.", mood: "idle", at: [1, 0.15] },
  { text: "Hold still, calibrating the camera.", mood: "idle", at: [0.5, 1] },
  { text: "You look tired. How about a short break?", mood: "alert", at: [0.1, 0.6] },
  { text: "Back to my corner. Call me if you need me.", mood: "idle", at: [0, 0] },
];
// Zones Gemma can pick, as a fraction of the free screen.
const SPOTS: Record<Spot, [number, number]> = {
  home: [0, 0],
  top_right: [1, 0.05],
  mid_left: [0, 0.5],
  mid_right: [1, 0.5],
  bottom_left: [0, 1],
  bottom_center: [0.5, 1],
  bottom_right: [1, 1],
};
// Mascot plus speech bubble plus both screen margins, so it never flies off screen.
const MASCOT_W = 192 + 12 + 260 + 64;
const MASCOT_H = 192 + 64;
// How long after PULSAR speaks the conversation stays open, so a spoken reply needs neither its name nor a question.
const ENGAGED_MS = 30_000;

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
  // MediaPipe runs in a worker over the live camera; it shows nothing and posts its numbers to the backend.
  const faceFrame = useRef<FaceFrame | null>(null);
  const biometrics = useFaceMetrics(videoRef, state === "live", faceFrame);
  const still = useReducedMotion();
  const [step, setStep] = useState(0);
  const [pos, setPos] = useState({ x: 0, y: 0 });
  const [heading, setHeading] = useState(0);
  // Last x, and the yaw that currently means "facing the camera" (grows by 2π on every spin).
  const face = useRef({ x: 0, front: 0 });
  // What the local vision model says it sees while WATCH is on, and the last thing the astronaut said.
  const [seen, setSeen] = useState<string | null>(null);
  // The astronaut's latest order (voice or typed): it stays in force while the camera keeps changing.
  const [instruction, setInstruction] = useState("");
  // Gemma's last decision (where to go, how to react, what to say); it overrides the mock script once it exists.
  const [directed, setDirected] = useState<Direction | null>(null);
  const said = useRef<string[]>([]);
  const turns = useRef<string[]>([]); // the conversation, oldest first: "Astronaut: ..." and "PULSAR: ..."
  const spokeAt = useRef(-Infinity); // when PULSAR last said something
  const spot = useRef<Spot>("home");
  const mock = MOCK_SCRIPT[step];
  const line = directed ? { text: directed.say, mood: directed.reaction === "alert" ? "alert" : "idle" as Mood, at: SPOTS[directed.spot || "home"] } : mock;
  const [tx, ty] = line.at;

  useEffect(() => {
    const id = setInterval(() => setStep((s) => (s + 1) % MOCK_SCRIPT.length), 7000);
    return () => clearInterval(id);
  }, []);

  // One call to Gemma, from either trigger. A stale answer never overwrites a newer one, and a silent one is dropped.
  const asked = useRef(0);
  const ask = useCallback((seenNow: string | null, order: string, userSpoke: boolean, viaVoice = false) => {
    const mine = ++asked.current;
    // WATCH is off, so there is no description: let Gemma look at the frame itself rather than answer blind.
    const frame = userSpoke && !seenNow ? frameBase64(videoRef.current).catch(() => undefined) : undefined;
    // For a while after PULSAR speaks, whatever the open microphone hears counts as a reply to it.
    const engaged = performance.now() - spokeAt.current < ENGAGED_MS;
    Promise.resolve(frame)
      .then((image) =>
        direct({ image, seen: seenNow ?? "", instruction: order, userSpoke, viaVoice, engaged, history: turns.current, said: said.current, spot: spot.current }),
      )
      .then((d) => {
        if (mine !== asked.current || !d.speak || !d.spot) return;
        spot.current = d.spot;
        said.current = [...said.current, d.say].slice(-5);
        // The backend compacts this further; here it only has to stay bounded.
        turns.current = [...turns.current, ...(userSpoke ? [`Astronaut: ${order}`] : []), `PULSAR: ${d.say}`].slice(-12);
        spokeAt.current = performance.now();
        if (userSpoke) setInstruction(order); // only words PULSAR took as meant for it become the standing instruction
        setDirected(d);
      })
      .catch(() => mine === asked.current && setDirected(null)); // backend or model down: back to the plain line
  }, [videoRef]);

  // The camera changed: Gemma speaks only if it matters for the standing instruction.
  const lastSeen = useRef<string | null>(null);
  useEffect(() => {
    if (seen && seen !== lastSeen.current) ask(seen, instruction, false);
    lastSeen.current = seen;
  }, [seen]); // eslint-disable-line react-hooks/exhaustive-deps

  // The astronaut typed (always answered) or spoke (answered when it was meant for PULSAR), using the latest description.
  const instruct = useCallback((text: string, spoken = false) => ask(lastSeen.current, text, true, spoken), [ask]);

  useEffect(() => {
    const [fx, fy] = still ? [0, 0] : [tx, ty];
    const next = { x: fx * Math.max(0, innerWidth - MASCOT_W), y: fy * Math.max(0, innerHeight - MASCOT_H) };
    setHeading(face.current.front + Math.sign(next.x - face.current.x) * 0.9); // look where it flies
    face.current.x = next.x;
    setPos(next);
  }, [tx, ty, still]);

  return (
    <main className="relative h-screen w-screen overflow-hidden bg-space">
      <video ref={videoRef} muted playsInline className="absolute inset-0 h-full w-full -scale-x-100 object-cover" />
      {state === "live" && <FaceOverlay frameRef={faceFrame} videoRef={videoRef} />}
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
        <PulsarMascot
          message={directed ? line.text : (seen ?? line.text)}
          mood={line.mood}
          heading={heading}
          tag={directed ? "GEMMA 4" : seen ? "CAMERA · AI DESCRIPTION" : "MOCK"}
        />
      </motion.div>

      <VerdictPanel biometrics={biometrics} />

      <SensesBar videoRef={videoRef} camLive={state === "live"} line={directed ? line.text : (seen ?? line.text)} onSeen={setSeen} onInstruction={instruct} />

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
