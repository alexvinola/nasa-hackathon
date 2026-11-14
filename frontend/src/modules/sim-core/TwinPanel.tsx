"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { Biometrics } from "@/modules/vision-hud/faceWorker";
import { BodyTwin } from "./BodyTwin";
import { GuidePanel } from "./GuidePanel";
import { GUIDES, formatReading, readingOf, statusOf, zoneStatus, type IndicatorStatus, type ZoneStatus } from "./indicators";
import { useTelemetry } from "./telemetryStore";

const EVERY_MS = 2000; // how often a camera reading goes to the store, and from there to the engine
const RETRY_MS = 5000; // how often the engine is asked for its rules while it has not listed them
const SYSTEMS = ["NERVOUS", "CARDIOVASCULAR", "RESPIRATORY", "MUSCULOSKELETAL", "METABOLIC", "IMMUNE"];

/**
 * The body twin over the HUD, bottom left, and the measurement guide it opens next to it. The twin shows each
 * indicator's reading and the engine's status; a click on one opens its guide. Both work with the camera off and
 * the backend down: the manual is still readable, the readings and statuses just say they are missing.
 */
export function TwinPanel({ biometrics }: { biometrics: Biometrics | null }) {
  const { telemetry, decision, rulebook, selfReportIsExample, setBiometrics, loadRulebook } = useTelemetry();
  const [selected, setSelected] = useState<string | null>(null);
  const [open, setOpen] = useState(true);

  const close = useCallback(() => setSelected(null), []);

  useEffect(() => {
    if (rulebook) return;
    loadRulebook();
    const id = setInterval(loadRulebook, RETRY_MS);
    return () => clearInterval(id);
  }, [rulebook, loadRulebook]);

  // shortcut: the twin asks the engine on its own, next to the verdict panel's loop (useVerdict); one store should
  // feed both once the sliders (G6) land. The camera's numbers change four times a second; it asks every two seconds.
  const sent = useRef(0);
  useEffect(() => {
    if (!biometrics || Date.now() - sent.current < EVERY_MS) return;
    sent.current = Date.now();
    setBiometrics(biometrics);
  }, [biometrics, setBiometrics]);

  const rules = rulebook?.rules ?? null;
  const readings: Record<string, string | null> = {};
  const statuses: Record<string, IndicatorStatus> = {};
  for (const guide of GUIDES) {
    const value = readingOf(telemetry, guide.signal);
    readings[guide.signal] = formatReading(value, guide.unit);
    statuses[guide.signal] = statusOf(guide, value, decision, rules);
  }
  const zones: Record<string, ZoneStatus> = {};
  for (const system of SYSTEMS) zones[system] = zoneStatus(system, decision, rules);

  const guide = GUIDES.find((g) => g.signal === selected);

  return (
    <div className="pointer-events-none absolute bottom-14 left-8 top-6 z-10 flex items-end gap-3">
      <section className="pointer-events-auto rounded-lg border border-pulse/30 bg-space/70 p-2 backdrop-blur">
        <header className="flex items-center gap-2 text-[10px] tracking-[0.2em] text-pulse">
          <span>BODY TWIN</span>
          <span className="text-shell/50">· TAP FOR A GUIDE</span>
          <button type="button" onClick={() => setOpen(!open)} aria-expanded={open} aria-label={open ? "Hide the body twin" : "Show the body twin"} className="ml-auto border border-shell/30 px-1.5 text-shell/70 hover:border-pulse hover:text-pulse">
            {open ? "–" : "+"}
          </button>
        </header>
        {open && (
          <>
            <div className="mt-2">
              <BodyTwin readings={readings} statuses={statuses} zones={zones} selected={selected} onSelect={setSelected} />
            </div>
            <p className="mt-1 text-[9px] tracking-[0.12em] text-shell/40">
              {telemetry
                ? selfReportIsExample ? "SLEEP AND MOOD ARE EXAMPLE DATA" : "ZONES SHOW THE RULES ENGINE'S VERDICT"
                : "NO READINGS YET · GUIDES STILL WORK"}
            </p>
          </>
        )}
      </section>

      {guide && (
        // Clear of the senses bar at the bottom; a new guide starts again at its first step.
        <div className="flex h-full flex-col justify-end pb-28">
          <GuidePanel
            key={guide.signal}
            guide={guide}
            reading={readings[guide.signal]}
            status={statuses[guide.signal]}
            example={selfReportIsExample && guide.signal.startsWith("selfReport.")}
            rulebook={rulebook}
            onClose={close}
          />
        </div>
      )}
    </div>
  );
}
