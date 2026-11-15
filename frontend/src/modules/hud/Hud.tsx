"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { motion, useReducedMotion } from "framer-motion";
import { AlertIndicator } from "./AlertIndicator";
import { LEFT_COLUMN_ID } from "./HudPanel";
import { PulsarMascot } from "./PulsarMascot";
import { ReactionTest } from "./ReactionTest";
import { useAlarmSound, type AlarmLevel } from "./useAlarmSound";
import { useHotkey } from "./useHotkey";
import { useWebcam, type CamState } from "./useWebcam";
import { SensesBar } from "@/modules/voice-ai/SensesBar";
import { VerdictPanel } from "@/modules/voice-ai/VerdictPanel";
import { useVerdict } from "@/modules/voice-ai/useVerdict";
import { countermeasureSteps, listRules, telemetryFrom, type Rule } from "@/modules/voice-ai/verdictApi";
import { GuidePanel } from "@/modules/guides/GuidePanel";
import { MiniTwin } from "@/modules/guides/MiniTwin";
import { HabitsPanel } from "@/modules/habits/HabitsPanel";
import { RelaxDock } from "@/modules/relax/RelaxDock";
import { HealthPanel } from "@/modules/guides/HealthPanel";
import { HEALTH_POINTS } from "@/modules/guides/healthPoints";
import { GUIDES, currentValue, statusOf } from "@/modules/guides/guides";
import { SelfReportPanel } from "@/modules/guides/SelfReportPanel";
import { FIELDS, isValid, type Entries } from "@/modules/guides/selfReport";
import { dispatchHudAction, useHudAction } from "./hudActions";
import { todayHabits } from "@/modules/habits/habitStore";
import { useFaceMetrics } from "@/modules/vision-hud/useFaceMetrics";
import { FaceOverlay } from "@/modules/vision-hud/FaceOverlay";
import type { Biometrics, FaceFrame } from "@/modules/vision-hud/faceWorker";
import { DebugPanel } from "@/modules/sim-core/DebugPanel";
import { LogPanel } from "@/modules/sim-core/LogPanel";
import { useSimVitals, type SimMode } from "@/modules/sim-core/useSimVitals";
import { setLang, useT } from "@/i18n";
import { LangToggle } from "@/i18n/LangToggle";
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
const RADIATION_SIGNAL = "environment.radiation_mSv";
// With nothing to react to, PULSAR drifts to the next of these every so often instead of sitting in its corner.
const WANDER: Spot[] = ["top_right", "bottom_right", "bottom_left", "home"];
const WANDER_EVERY_MS = 20_000;
// A question about what is in view gets the camera frame attached, so Gemma answers from the picture. Anything else
// goes without it: on a CPU-only laptop the picture alone adds several seconds to the answer.
const ABOUT_THE_VIEW = /\b(see|look|watch|show|camera|picture|image|view|holding|wearing|behind|colou?r|how many|who is|what is (this|that)|what am i|ves|veo|ver|mira|muestra|ense[nñ]a|c[aá]mara|imagen|foto|tengo|llevo|detr[aá]s|color|cu[aá]nt[oa]s|qui[eé]n es|qu[eé] es (esto|eso))\b/i;

const CAM_KEY = {
  starting: "hud.cam.starting",
  live: "hud.cam.live",
  denied: "hud.cam.denied",
  unavailable: "hud.cam.unavailable",
} as const satisfies Record<CamState, string>;

function Corner({ className }: { className: string }) {
  return <span className={`absolute h-8 w-8 ${className}`} />;
}

/** Full-screen camera with the HUD layered on top. Every line PULSAR says comes from the rules engine or Gemma. */
export function Hud() {
  const t = useT();
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
  // What the astronaut typed in from the devices (guides/SelfReportPanel): it replaces the example's self-report,
  // and a pulse counted by hand replaces the simulated one.
  const [entries, setEntries] = useState<Entries>({});
  const [reporting, setReporting] = useState(false); // opens from a body marker, the R key, or PULSAR
  const [devTools, setDevTools] = useState(false);
  useHotkey("r", () => setReporting((was) => !was));
  const reading = useMemo<Biometrics>(() => {
    const base = measured && simMode === "live" ? { ...measured, heartRateBpm: sim.vitals.heartRateBpm, heartRateConfidence: 0 } : sim.vitals;
    return entries.heartRateBpm == null ? base : { ...base, heartRateBpm: entries.heartRateBpm, heartRateConfidence: 1 };
  }, [measured, simMode, sim.vitals, entries.heartRateBpm]);
  const telemetryNow = useRef(telemetryFrom(reading, sim.cabinCo2, sim.radiation, entries));
  telemetryNow.current = telemetryFrom(reading, sim.cabinCo2, sim.radiation, entries);
  // The rules engine decides on those readings and Gemma phrases its verdict.
  const { decision, advice, error } = useVerdict(reading, sim.cabinCo2, sim.radiation, entries, simMode);
  // The engine's own CO2 limit, for the cabin-air gauge: the HUD never hard-codes a threshold.
  const [rules, setRules] = useState<Rule[]>([]);
  useEffect(() => {
    listRules().then(setRules).catch(() => undefined);
  }, []);
  const co2Limit = rules.find((rule) => rule.signal === CO2_SIGNAL)?.threshold ?? null;
  const perclosLimit = rules.find((rule) => rule.signal === DROWSY_SIGNAL)?.threshold ?? null;
  const fatigueLimit = rules.find((rule) => rule.signal === EXHAUSTED_SIGNAL)?.threshold ?? null;
  const radiationLimit = rules.find((rule) => rule.signal === RADIATION_SIGNAL)?.threshold ?? null;
  // The indicator guide that is open (G9), by contract signal, and the engine's status for each indicator.
  const [guideSignal, setGuideSignal] = useState<string | null>(null);
  const guide = GUIDES.find((candidate) => candidate.signal === guideSignal);
  // A marker (or an alarm's link) opens the measurement form on that signal: the guide and the form are one panel.
  const openGuide = (signal: string) => {
    setHealthId(null);
    setGuideSignal(signal);
    setReporting(true);
  };
  // The presentation (docs/brand/pulsar-intro.html) embeds this HUD and runs its three demo cues here: 1 the live
  // readings, 2 a drowsiness warning, 3 danger and PULSAR's response. Only those three words are accepted, and only
  // from the window that embeds the HUD. The readings are forced through the debug panel's own modes, not measured.
  useEffect(() => {
    const modes: Record<string, SimMode> = { measure: "live", sleep: "rest", alert: "danger" };
    const on = (event: MessageEvent) => {
      if (window.parent === window || event.source !== window.parent) return;
      const language = event.data?.pulsarDemoLang;
      if (language === "es" || language === "en") return setLang(language);
      const phase = event.data?.pulsarDemoPhase;
      if (typeof phase !== "string" || !Object.hasOwn(modes, phase)) return;
      setSimMode(modes[phase]);
      setReporting(false);
      setGuideSignal(null);
      setHealthId(null);
    };
    window.addEventListener("message", on);
    if (window.parent !== window) window.parent.postMessage({ pulsarDemoReady: true }, "*"); // no data: it only asks for the language
    return () => window.removeEventListener("message", on);
  }, []);
  // PULSAR was asked, by voice or chat, to open a measurement or to type one in. The values are checked again here
  // against the contract's bounds, as if they had been typed in the form.
  useHudAction((action) => {
    if (action.type === "open_measure") {
      if (action.signal) openGuide(action.signal);
      else {
        setHealthId(null);
        setReporting(true);
      }
    } else if (action.type === "set_measure") {
      const fields = FIELDS[action.signal];
      if (!fields || !fields.every((f) => isValid(f, action.values[f.key]))) return;
      // Saved, and the measurement's form opens on that signal with the value in it, so it can be checked or corrected.
      setEntries((had) => ({ ...had, ...Object.fromEntries(fields.map((f) => [f.key, action.values[f.key]])) }));
      openGuide(action.signal);
    } else if (action.type === "open_health") {
      if (action.id === null) return; // only the symptoms tab: MiniTwin switches to it
      if (!HEALTH_POINTS.some((point) => point.id === action.id)) return;
      setGuideSignal(null);
      setReporting(false);
      setHealthId(action.id);
    } else if (action.type === "close_panels") {
      setReporting(false);
      setGuideSignal(null);
      setHealthId(null);
    } else if (action.type === "set_language") {
      setLang(action.lang);
    } else if (action.type === "dev_menu") {
      setDevTools(action.open);
    } else if (action.type === "set_overlay") {
      setDevTools(true); // the face mesh and AI check switches live in the developer menu: show them
    }
  });
  // The SALUD point whose panel is open (id in guides/healthPoints.ts); it shares the place of the guides, so one at a time.
  const [healthId, setHealthId] = useState<string | null>(null);
  const healthPoint = HEALTH_POINTS.find((candidate) => candidate.id === healthId);
  const guideStatuses = Object.fromEntries(GUIDES.map((candidate) => [candidate.signal, statusOf(candidate, decision, rules)]));

  // Two alarm levels, both read off the engine's verdict and never decided here: amber "time to rest" when it
  // finds the astronaut drowsy, red "danger" for anything it rates RED (exhaustion included).
  const flagged = (signal: string) => !!decision?.factors.some((f) => f.signal === signal);
  // Amber with a finding about the surroundings (cabin air) is a "warn": a warning with its steps, no reaction test.
  const surroundings = decision?.status === "AMBER" && decision.factors.some((f) => f.signal.startsWith("environment."));
  const level: AlarmLevel = decision?.status === "RED" ? "danger" : flagged(DROWSY_SIGNAL) ? "rest" : surroundings ? "warn" : null;
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
  // A radiation or cabin-air alarm has nothing to do with reactions: pressing the button just acknowledges it.
  const radiationOnly = (flagged(RADIATION_SIGNAL) || level === "warn") && !flagged(EXHAUSTED_SIGNAL) && !flagged(DROWSY_SIGNAL);
  const acknowledged = !!level && (ackedLevel === level || ackedLevel === "danger");
  const ringing: AlarmLevel = acknowledged ? null : level;
  // One sound per alarm level: forcing an alarm that is already on changes nothing here, so it cannot start another.
  // Quiet during the test, so the siren does not slow the reactions it is measuring.
  useAlarmSound(sound && !testing ? ringing : null);
  // An alarm outranks a guide: the open guide closes so it never covers the alert and its steps.
  useEffect(() => {
    if (ringing) {
      setGuideSignal(null);
      setHealthId(null);
    }
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
          habits: todayHabits(),
          telemetry: telemetryNow.current, // so PULSAR knows the engine's current health check
        }),
      )
      .then((d) => {
        if (mine !== asked.current || !d.speak || !d.spot) return;
        moveTo(d.spot);
        setDirected(d);
        say(d.say, order);
        for (const action of d.actions ?? (d.action ? [d.action] : [])) dispatchHudAction(action);
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

  const edge = ringing === "danger" ? "border-red-500" : (ringing === "rest" || ringing === "warn") ? "border-amber-400" : "border-pulse/80";

  return (
    <main className="relative h-screen w-screen overflow-hidden bg-space">
      <video ref={videoRef} muted playsInline className="absolute inset-0 h-full w-full -scale-x-100 object-cover" />
      {/* The left column of foldable panels, below the mascot's home corner. Declared before the camera overlay,
          whose AI-check panel joins it through a portal. */}
      {/* The column runs from the top to above the footer line and only scrolls when the panels truly do not fit. */}
      <div id={LEFT_COLUMN_ID} className="pointer-events-none absolute bottom-20 left-8 top-8 z-[1] [&>*]:pointer-events-auto flex w-64 flex-col gap-2 overflow-y-auto [scrollbar-color:var(--color-pulse)_transparent] [scrollbar-width:thin]">
        {/* Relajarse, Asistente and Hábitos stay at the top; the AI check and the debug panels (settings button) open below them. */}
        <MiniTwin
          statuses={guideStatuses}
          open={guideSignal}
          onOpen={openGuide}
          healthOpen={healthId}
          onOpenHealth={(id) => {
            setGuideSignal(null);
            setReporting(false);
            setHealthId(id);
          }}
        />
        <HabitsPanel sleepHours={entries.sleepHoursLast24h} />
        {/* Hidden, not unmounted, so their hotkeys keep working; right-click the version to show them. */}
        <div className={devTools ? "contents" : "hidden"}>
          <DebugPanel mode={simMode} onMode={setSimMode} sound={sound} onSound={setSound} />
          <LogPanel />
        </div>
      </div>
      {state === "live" && <FaceOverlay frameRef={faceFrame} videoRef={videoRef} problem={faceProblem} menu={devTools} />}
      {state !== "live" && (
        <div className="absolute inset-0 grid place-items-center bg-[radial-gradient(ellipse_at_center,var(--color-space-lift),var(--color-space))] text-sm tracking-widest text-orbit">
          {t(CAM_KEY[state])}
        </div>
      )}

      <div className="hud-scanlines pointer-events-none absolute inset-0" />
      <div className="hud-vignette pointer-events-none absolute inset-0" />

      {(ringing === "rest" || ringing === "warn") && <div className="hud-rest pointer-events-none absolute inset-0 border-4 border-amber-400" />}
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
        detail={
          level === "danger" && flagged(EXHAUSTED_SIGNAL) ? t("hud.detail.exhausted") : level === "danger" && radiationOnly ? t("hud.detail.radiation") : level === "warn" && flagged(CO2_SIGNAL) ? t("hud.detail.co2") : undefined
        }
        steps={steps}
        acknowledged={acknowledged}
        testing={testing}
        needsTest={!radiationOnly}
        onTest={() => (radiationOnly ? setAckedLevel(level) : setTesting(true))}
        // Closing the alert acknowledges it: the siren and the frame stop and the mascot goes back to normal.
        onClose={() => {
          setAckedLevel(level);
          setDirected(null);
        }}
      />

      <VerdictPanel
        biometrics={reading}
        decision={decision}
        error={error}
        simulated={!measured || simMode !== "live"}
        cabinCo2={sim.cabinCo2}
        cabinCo2Limit={co2Limit}
        radiation={sim.radiation}
        radiationLimit={radiationLimit}
        perclosLimit={perclosLimit}
        fatigueLimit={fatigueLimit}
        onOpenGuide={openGuide}
      />

      {reporting && (
        <SelfReportPanel
          entries={entries}
          statuses={guideStatuses}
          signal={guideSignal}
          onSelect={setGuideSignal}
          valueOf={(signal) => currentValue(signal, telemetryNow.current)}
          onSave={(values) => setEntries((had) => ({ ...had, ...values }))}
          onClear={(keys) => setEntries((had) => Object.fromEntries(Object.entries(had).filter(([key]) => !keys.includes(key))))}
          onClose={() => {
            setReporting(false);
            setGuideSignal(null);
          }}
        />
      )}

      {guide && !reporting && (
        <GuidePanel
          key={guide.signal}
          guide={guide}
          value={currentValue(guide.signal, telemetryNow.current)}
          status={guideStatuses[guide.signal]}
          onClose={() => setGuideSignal(null)}
        />
      )}

      {healthPoint && !reporting && <HealthPanel key={healthPoint.id} point={healthPoint} onClose={() => setHealthId(null)} />}

      <RelaxDock suggest={level === "rest"} />

      <SensesBar line={bubble} onInstruction={instruct} />

      {state !== "live" && (
        <div className="absolute right-8 top-8 bg-space/90 px-2 py-1 text-right text-xs font-bold tracking-[0.2em] text-amber-300">● {t(CAM_KEY[state])}</div>
      )}

      <div className="absolute bottom-8 left-8 flex items-center gap-3 text-xs tracking-[0.2em] text-shell/70">
        <LangToggle className="pointer-events-auto" />
        {/* A gear instead of the version text; click it for the developer panels. */}
        <button
          type="button"
          aria-pressed={devTools}
          aria-label={t("hud.version")}
          title={t("hud.version")}
          className="hud-btn pointer-events-auto grid h-8 w-8 place-items-center backdrop-blur"
          onClick={() => setDevTools((was) => !was)}
        >
          <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
            <circle cx="12" cy="12" r="3" />
            <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09a1.65 1.65 0 0 0-1-1.51 1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09a1.65 1.65 0 0 0 1.51-1 1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33h0a1.65 1.65 0 0 0 1-1.51V3a2 2 0 1 1 4 0v.09a1.65 1.65 0 0 0 1 1.51h0a1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82v0a1.65 1.65 0 0 0 1.51 1H21a2 2 0 1 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
          </svg>
        </button>
      </div>

      {/* Stays open even if the readings flicker back to clear mid-test. */}
      {testing && (
        <ReactionTest steps={steps} onAcknowledge={() => setAckedLevel(level)} onClose={() => setTesting(false)} />
      )}
    </main>
  );
}
