"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { motion, useReducedMotion } from "framer-motion";
import { AlertIndicator } from "./AlertIndicator";
import { LEFT_COLUMN_ID } from "./HudPanel";
import { PulsarMascot } from "./PulsarMascot";
import { ReactionTest } from "./ReactionTest";
import { useAlarmSound, type AlarmLevel } from "./useAlarmSound";
import { useWebcam, type CamState } from "./useWebcam";
import { SensesBar } from "@/modules/voice-ai/SensesBar";
import { VerdictPanel } from "@/modules/voice-ai/VerdictPanel";
import { useVerdict } from "@/modules/voice-ai/useVerdict";
import { countermeasureSteps, listRules, telemetryFrom, type Rule } from "@/modules/voice-ai/verdictApi";
import { GuidePanel } from "@/modules/guides/GuidePanel";
import { MiniTwin } from "@/modules/guides/MiniTwin";
import { GUIDES, currentValue, statusOf } from "@/modules/guides/guides";
import { useFaceMetrics } from "@/modules/vision-hud/useFaceMetrics";
import { FaceOverlay } from "@/modules/vision-hud/FaceOverlay";
import type { Biometrics, FaceFrame } from "@/modules/vision-hud/faceWorker";
import { DebugPanel } from "@/modules/sim-core/DebugPanel";
import { useSimVitals, type SimMode } from "@/modules/sim-core/useSimVitals";
import { direct, frameBase64, type Direction, type Spot } from "@/modules/voice-ai/pulsarApi";

// Zones Gemma can pick, as a fraction of the free screen; [0, 0] is PULSAR's home corner.
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
const MASCOT_W = 192 + 12 + 340 + 64;
const MASCOT_H = 192 + 64;
// The same without the margins (what must not overlap a panel), its home offset from the screen edge, and the gap
// kept around panels.
const MASCOT_BOX_W = 192 + 12 + 340;
const MASCOT_BOX_H = 192;
const HOME = 32;
const GAP = 12;
const PANEL_RESERVE = 352; // the verdict panel on the right: 20rem wide plus its 2rem margin
// Where PULSAR goes during an alarm, as a fraction of the free screen.
const CENTER: [number, number] = [0.5, 0.5];
// The engine signals behind the two alarms: eyes closed too much of the time (rule `perclos-high`) and a fatigue
// score past the unsafe level (rule `fatigue-score-high`).
const DROWSY_SIGNAL = "biometrics.perclos";
const EXHAUSTED_SIGNAL = "biometrics.fatigueScore";
const CO2_SIGNAL = "environment.cabinCo2_mmHg";
// With nothing to react to, PULSAR drifts to the next of these every so often instead of sitting in its corner.
const WANDER: Spot[] = ["top_right", "bottom_right", "bottom_left", "home"];
const WANDER_EVERY_MS = 20_000;
// A question about what is in view gets the camera frame attached, so Gemma answers from the picture. Anything else
// goes without it: on a CPU-only laptop the picture alone adds several seconds to the answer.
const ABOUT_THE_VIEW = /\b(see|look|watch|show|camera|picture|image|view|holding|wearing|behind|colou?r|how many|who is|what is (this|that)|what am i|ves|mira|c[aá]mara|imagen)\b/i;

const CAM_LABEL: Record<CamState, string> = {
  starting: "CAM · STARTING",
  live: "CAM · LIVE",
  denied: "CAM · PERMISSION DENIED",
  unavailable: "CAM · NOT AVAILABLE",
};

function Corner({ className }: { className: string }) {
  return <span className={`absolute h-8 w-8 ${className}`} />;
}

/** Full-screen camera with the HUD layered on top. Every line PULSAR says comes from the rules engine or Gemma. */
export function Hud() {
  const { videoRef, state } = useWebcam();
  // MediaPipe runs in a worker over the live camera; it shows nothing and posts its numbers to the backend.
  const faceFrame = useRef<FaceFrame | null>(null);
  const [faceProblem, setFaceProblem] = useState("");
  const measured = useFaceMetrics(videoRef, state === "live", faceFrame, setFaceProblem);
  // The debug panel can force a false alarm or loop a simulated shift, and mute the alarm sounds.
  const [simMode, setSimMode] = useState<SimMode>("live");
  const [sound, setSound] = useState(true);
  const sim = useSimVitals(simMode);
  // Camera readings when there is a camera and nothing is forced, simulated ones otherwise. The pulse is simulated
  // either way: nothing measures it yet.
  const reading = useMemo<Biometrics>(
    () => (measured && simMode === "live" ? { ...measured, heartRateBpm: sim.vitals.heartRateBpm, heartRateConfidence: 0 } : sim.vitals),
    [measured, simMode, sim.vitals],
  );
  const telemetryNow = useRef(telemetryFrom(reading, sim.cabinCo2));
  telemetryNow.current = telemetryFrom(reading, sim.cabinCo2);
  // The rules engine decides on those readings and Gemma phrases its verdict.
  const { decision, advice, error } = useVerdict(reading, sim.cabinCo2);
  // The engine's own CO2 limit, for the cabin-air gauge: the HUD never hard-codes a threshold.
  const [rules, setRules] = useState<Rule[]>([]);
  useEffect(() => {
    listRules().then(setRules).catch(() => undefined);
  }, []);
  const co2Limit = rules.find((rule) => rule.signal === CO2_SIGNAL)?.threshold ?? null;
  // The indicator guide that is open (G9), by contract signal, and the engine's status for each indicator.
  const [guideSignal, setGuideSignal] = useState<string | null>(null);
  const guide = GUIDES.find((candidate) => candidate.signal === guideSignal);
  const guideStatuses = Object.fromEntries(GUIDES.map((candidate) => [candidate.signal, statusOf(candidate, decision, rules)]));

  // Two alarm levels, both read off the engine's verdict and never decided here: amber "time to rest" when it
  // finds the astronaut drowsy, red "danger" for anything it rates RED (exhaustion included).
  const flagged = (signal: string) => !!decision?.factors.some((f) => f.signal === signal);
  const level: AlarmLevel = decision?.status === "RED" ? "danger" : flagged(DROWSY_SIGNAL) ? "rest" : null;
  // The astronaut stops an alarm by acknowledging it: the sound and the pulsing frame end, the indicator stays
  // until the readings clear. It rings again only for a later alarm, or if this one worsens from rest to danger.
  const [ackedLevel, setAckedLevel] = useState<AlarmLevel>(null);
  // Acknowledging means taking the reaction test: passing it stops the alarm, failing it says what to do instead.
  const [testing, setTesting] = useState(false);
  useEffect(() => {
    if (!level) setAckedLevel(null);
  }, [level]);
  // A forced alarm switched off and on again is a new alarm, even when the engine never saw the gap between them.
  useEffect(() => setAckedLevel(null), [simMode]);
  const acknowledged = !!level && (ackedLevel === level || ackedLevel === "danger");
  const ringing: AlarmLevel = acknowledged ? null : level;
  // One sound per alarm level: forcing an alarm that is already on changes nothing here, so it cannot start another.
  // Quiet during the test, so the siren does not slow the reactions it is measuring.
  useAlarmSound(sound && !testing ? ringing : null);
  // An alarm outranks a guide: the open guide closes so it never covers the alert and its steps.
  useEffect(() => {
    if (ringing) setGuideSignal(null);
  }, [ringing]);
  // What to do about it: the steps of the countermeasure the engine picked, shown on the alert indicator.
  const [steps, setSteps] = useState<string[]>([]);
  const countermeasure = level ? decision?.countermeasureId : null;
  useEffect(() => {
    setSteps([]);
    if (!countermeasure) return;
    let on = true;
    countermeasureSteps(countermeasure).then((s) => on && setSteps(s)).catch(() => undefined);
    return () => {
      on = false;
    };
  }, [countermeasure]);

  const still = useReducedMotion();
  const [pos, setPos] = useState({ x: 0, y: 0 });
  const [heading, setHeading] = useState(0);
  // Last x, and the yaw that currently means "facing the camera" (grows by 2π on every spin).
  const face = useRef({ x: 0, front: 0 });
  // Gemma's last stage direction: where the mascot is and how it reacts.
  const [directed, setDirected] = useState<Direction | null>(null);
  // What the mascot is saying, whoever produced it last: the engine's finding, Gemma's phrasing of it, or an answer.
  const [bubble, setBubble] = useState("");
  const said = useRef<string[]>([]);
  const turns = useRef<string[]>([]); // the conversation, oldest first: "Astronaut: ..." and "PULSAR: ..."
  // Where the mascot is: Gemma's choice after a turn, the middle of the view during an alarm, wandering otherwise.
  const [at, setAt] = useState<Spot>("home");
  const spot = useRef<Spot>("home");
  spot.current = at;
  const movedAt = useRef(0);
  const moveTo = useCallback((next: Spot) => {
    movedAt.current = performance.now();
    setAt(next);
  }, []);
  const [tx, ty] = ringing ? CENTER : SPOTS[at];

  useEffect(() => {
    if (ringing) return;
    const id = setInterval(() => {
      if (performance.now() - movedAt.current < WANDER_EVERY_MS) return; // Gemma moved it recently: leave it there
      moveTo(WANDER[(WANDER.indexOf(spot.current) + 1) % WANDER.length]);
    }, 1000);
    return () => clearInterval(id);
  }, [ringing, moveTo]);

  /** PULSAR says `text`: on the mascot and in its memory. SPEAK reads it aloud. */
  const say = useCallback((text: string, heard?: string) => {
    said.current = [...said.current, text].slice(-5);
    // The backend compacts this further; here it only has to stay bounded.
    turns.current = [...turns.current, ...(heard ? [`Astronaut: ${heard}`] : []), `PULSAR: ${text}`].slice(-12);
    setBubble(text);
  }, []);

  // The verdict changed: the mascot shows the engine's own finding at once, because Gemma needs several seconds
  // to phrase it and an alarm must not wait for wording. Back to all clear, the old warning is dropped.
  const reason = decision ? `${decision.status}|${decision.factors.map((f) => f.signal).join(",")}` : "";
  useEffect(() => {
    setBubble(decision?.factors[0]?.message ?? "");
  }, [reason]); // eslint-disable-line react-hooks/exhaustive-deps

  // Gemma's phrasing of that verdict arrives: the mascot says it.
  useEffect(() => {
    if (advice) say(advice.say);
  }, [advice, say]);

  // The astronaut typed or held the talk button: one call to Gemma, always answered. A stale answer never
  // overwrites a newer one.
  const asked = useRef(0);
  const instruct = useCallback((order: string) => {
    const mine = ++asked.current;
    const frame = ABOUT_THE_VIEW.test(order) ? frameBase64(videoRef.current).catch(() => undefined) : undefined;
    Promise.resolve(frame)
      .then((image) =>
        direct({
          image,
          instruction: order,
          userSpoke: true,
          history: turns.current,
          said: said.current,
          spot: spot.current,
          telemetry: telemetryNow.current, // so PULSAR knows the engine's current health check
        }),
      )
      .then((d) => {
        if (mine !== asked.current || !d.speak || !d.spot) return;
        moveTo(d.spot);
        setDirected(d);
        say(d.say, order);
      })
      .catch(() => undefined); // backend or model down: the mascot keeps its last line
  }, [videoRef, say, moveTo]);

  useEffect(() => {
    const [fx, fy] = still ? [0, 0] : [tx, ty];
    const next = { x: fx * Math.max(0, innerWidth - MASCOT_W), y: fy * Math.max(0, innerHeight - MASCOT_H) };
    // During an alarm, centre it in the width left of the verdict panel instead of the whole screen.
    if (ringing && !still) next.x = Math.max(0, (innerWidth - PANEL_RESERVE - MASCOT_BOX_W) / 2 - HOME);
    // Never park over a panel. Try the wanted place and every place that sits flush against a panel or a screen
    // edge, and take the one that covers no panel and is nearest to where it wanted to go. On a window too small
    // to have such a place, it takes the one that covers least.
    const panels = [...document.querySelectorAll("[data-hud-panel]")].map((panel) => panel.getBoundingClientRect());
    const maxX = Math.max(0, innerWidth - MASCOT_W);
    const maxY = Math.max(0, innerHeight - MASCOT_H);
    const covered = (x: number, y: number) =>
      panels.reduce((area, r) => {
        const w = Math.min(HOME + x + MASCOT_BOX_W + GAP, r.right) - Math.max(HOME + x - GAP, r.left);
        const h = Math.min(HOME + y + MASCOT_BOX_H + GAP, r.bottom) - Math.max(HOME + y - GAP, r.top);
        return area + (w > 0 && h > 0 ? w * h : 0);
      }, 0);
    const want = { x: Math.min(next.x, maxX), y: Math.min(next.y, maxY) };
    const xs = [want.x, 0, maxX, ...panels.flatMap((r) => [r.right + GAP - HOME, r.left - GAP - MASCOT_BOX_W - HOME])];
    const ys = [want.y, 0, maxY, ...panels.flatMap((r) => [r.bottom + GAP - HOME, r.top - GAP - MASCOT_BOX_H - HOME])];
    let cost = Infinity;
    for (const x of xs.filter((x) => x >= 0 && x <= maxX)) {
      for (const y of ys.filter((y) => y >= 0 && y <= maxY)) {
        const c = covered(x, y) * 1e6 + Math.hypot(x - want.x, y - want.y);
        if (c < cost) [cost, next.x, next.y] = [c, x, y];
      }
    }
    setHeading(face.current.front + Math.sign(next.x - face.current.x) * 0.9); // look where it flies
    face.current.x = next.x;
    setPos(next);
  }, [tx, ty, still, level, ringing, steps, reason, state, guideSignal]); // the panels come and go with the alarm and the camera

  const edge = ringing === "danger" ? "border-red-500" : ringing === "rest" ? "border-amber-400" : "border-pulse/80";

  return (
    <main className="relative h-screen w-screen overflow-hidden bg-space">
      <video ref={videoRef} muted playsInline className="absolute inset-0 h-full w-full -scale-x-100 object-cover" />
      {/* The left column of foldable panels, below the mascot's home corner. Declared before the camera overlay,
          whose AI-check panel joins it through a portal. */}
      <div id={LEFT_COLUMN_ID} className="absolute left-8 top-60 z-[1] flex max-h-[calc(100vh-18rem)] w-64 flex-col gap-2 overflow-y-auto">
        <MiniTwin statuses={guideStatuses} open={guideSignal} onOpen={setGuideSignal} />
        <DebugPanel mode={simMode} onMode={setSimMode} sound={sound} onSound={setSound} />
      </div>
      {state === "live" && <FaceOverlay frameRef={faceFrame} videoRef={videoRef} problem={faceProblem} />}
      {state !== "live" && (
        <div className="absolute inset-0 grid place-items-center bg-[radial-gradient(ellipse_at_center,var(--color-space-lift),var(--color-space))] text-sm tracking-widest text-orbit">
          {CAM_LABEL[state]}
        </div>
      )}

      <div className="hud-scanlines pointer-events-none absolute inset-0" />
      <div className="hud-vignette pointer-events-none absolute inset-0" />

      {ringing === "rest" && <div className="hud-rest pointer-events-none absolute inset-0 border-4 border-amber-400" />}
      {ringing === "danger" && <div className="hud-danger pointer-events-none absolute inset-0 border-8 border-red-600" />}

      <div className="pointer-events-none absolute inset-4">
        <Corner className={`left-0 top-0 border-l-2 border-t-2 ${edge}`} />
        <Corner className={`right-0 top-0 border-r-2 border-t-2 ${edge}`} />
        <Corner className={`bottom-0 left-0 border-b-2 border-l-2 ${edge}`} />
        <Corner className={`bottom-0 right-0 border-b-2 border-r-2 ${edge}`} />
      </div>

      <motion.div
        className="pointer-events-none absolute left-8 top-8"
        animate={pos}
        transition={{ duration: 2.4, ease: "easeInOut" }}
        onAnimationComplete={() => {
          if (!pos.x && !pos.y) face.current.front += 2 * Math.PI; // home again: one full spin
          setHeading(face.current.front);
        }}
      >
        <PulsarMascot
          message={bubble}
          mood={ringing || directed?.reaction === "alert" ? "alert" : "idle"}
          heading={heading}
          bpm={reading.heartRateBpm}
        />
      </motion.div>

      <AlertIndicator
        level={level}
        detail={level === "danger" && flagged(EXHAUSTED_SIGNAL) ? "NOT SAFE TO STAY AWAKE" : undefined}
        steps={steps}
        acknowledged={acknowledged}
        testing={testing}
        onTest={() => setTesting(true)}
      />

      <VerdictPanel
        biometrics={reading}
        decision={decision}
        advice={advice}
        error={error}
        simulated={!measured || simMode !== "live"}
        cabinCo2={sim.cabinCo2}
        cabinCo2Limit={co2Limit}
        onOpenGuide={setGuideSignal}
      />

      {guide && (
        <GuidePanel
          key={guide.signal}
          guide={guide}
          value={currentValue(guide.signal, telemetryNow.current)}
          status={guideStatuses[guide.signal]}
          onClose={() => setGuideSignal(null)}
        />
      )}

      <SensesBar line={bubble} onInstruction={instruct} />

      <div className="absolute right-8 top-8 bg-space/90 px-2 py-1 text-right text-xs font-bold tracking-[0.2em] text-pulse">
        <div className={state === "live" ? "" : "text-amber-300"}>● {CAM_LABEL[state]}</div>
        <div className="mt-1 text-shell">OFFLINE · LOCAL ONLY</div>
      </div>

      <div className="absolute inset-x-8 bottom-8 flex items-end justify-between text-xs tracking-[0.2em] text-shell/70">
        <span className="bg-space/90 px-2 py-1 text-shell">PULSAR HUD · v0.1</span>
        <span className="bg-space/90 px-2 py-1 font-bold text-amber-300">NOT A MEDICAL DEVICE</span>
      </div>

      {/* Stays open even if the readings flicker back to clear mid-test. */}
      {testing && (
        <ReactionTest steps={steps} onAcknowledge={() => setAckedLevel(level)} onClose={() => setTesting(false)} />
      )}
    </main>
  );
}
