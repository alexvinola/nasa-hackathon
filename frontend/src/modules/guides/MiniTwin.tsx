"use client";

import { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { createRenderer, releaseRenderer } from "@/modules/hud/glRenderer";
import { HudPanel } from "@/modules/hud/HudPanel";
import { useHudAction } from "@/modules/hud/hudActions";
import { HEALTH_POINTS } from "./healthPoints";
import { useLang, useT } from "@/i18n";
import { GUIDES, localizedGuide, type GuideStatus } from "./guides";
import { healthText } from "./healthPoints";
import { FIGURE_ASPECT, FIGURE_HALF_HEIGHT, SITE, disposeScene, lightScene, standingFigure, type V3 } from "./mannequin";

const HEIGHT = 288; // CSS pixels
const WIDTH = HEIGHT * FIGURE_ASPECT;

const DOT: Record<GuideStatus, string> = {
  GREEN: "border-emerald-300 bg-emerald-400/80",
  AMBER: "border-amber-200 bg-amber-400",
  RED: "border-red-200 bg-red-500",
  "NOT JUDGED": "border-orbit bg-orbit/70",
  WAITING: "border-shell/60 bg-shell/30",
};

/** The standing mannequin, seen straight from the front so the markers stay where the instruments go. */
function Figure() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let renderer: THREE.WebGLRenderer;
    try {
      renderer = createRenderer(canvasRef.current!, true);
    } catch {
      setFailed(true); // no WebGL: the markers alone still open the guides
      return;
    }
    renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
    renderer.setSize(WIDTH, HEIGHT, false);
    const scene = new THREE.Scene();
    lightScene(scene, false);
    const half = FIGURE_HALF_HEIGHT;
    const camera = new THREE.OrthographicCamera(-half * FIGURE_ASPECT, half * FIGURE_ASPECT, half, -half, 0.1, 20);
    camera.position.z = 6;
    scene.add(standingFigure());
    // Drawn once: the figure stands still, and the scan line over it is CSS, so the HUD pays nothing per frame.
    const raf = requestAnimationFrame(() => renderer.render(scene, camera));
    return () => {
      cancelAnimationFrame(raf);
      disposeScene(scene);
      releaseRenderer(renderer);
    };
  }, []);

  return failed ? null : (
    <>
      <canvas ref={canvasRef} aria-hidden className="absolute inset-0 h-full w-full" />
      <div aria-hidden className="twin-scan pointer-events-none absolute inset-x-0 top-0 h-px bg-pulse shadow-[0_0_8px] shadow-pulse" />
    </>
  );
}

/**
 * A small 3D body with one marker where each instrument is used. One click on a marker opens that indicator's
 * guide. This is only the entry to the guides; the full twin with sliders is G6.
 */
export function MiniTwin({
  statuses,
  open,
  onOpen,
  healthOpen,
  onOpenHealth,
}: {
  statuses: Record<string, GuideStatus>;
  /** Signal of the guide currently open, if any. */
  open: string | null;
  onOpen: (signal: string) => void;
  /** Id of the SALUD point whose panel is open, if any. */
  healthOpen: string | null;
  onOpenHealth: (id: string) => void;
}) {
  const t = useT();
  const lang = useLang();
  // "measure": a marker where each instrument is used. "health": a marker for each body zone NASA lists risks for.
  const [tab, setTab] = useState<"measure" | "health">("measure");
  // PULSAR was asked for symptoms or for a measurement: show the matching tab.
  useHudAction((action) => {
    if (action.type === "open_health") setTab("health");
    else if (action.type === "open_measure" || action.type === "set_measure") setTab("measure");
  });
  const TAB = "flex-1 border px-1 py-1 text-[11px] tracking-[0.08em]";
  const place = ([x, y]: V3) => ({
    left: `${((x / (FIGURE_HALF_HEIGHT * FIGURE_ASPECT) + 1) / 2) * 100}%`,
    top: `${((1 - y / FIGURE_HALF_HEIGHT) / 2) * 100}%`,
  });
  return (
    <HudPanel title={t("guides.twin.title")} data-twin>
      <div role="tablist" aria-label={t("guides.twin.tabsAria")} className="mb-2 flex gap-1">
        {([["measure", t("guides.twin.tabMeasure")], ["health", t("guides.twin.tabHealth")]] as const).map(([id, label]) => (
          <button
            key={id}
            type="button"
            role="tab"
            aria-selected={tab === id}
            onClick={() => setTab(id)}
            className={`${TAB} ${tab === id ? "border-pulse bg-pulse/20 text-pulse" : "border-shell/40 text-shell/80"}`}
          >
            {label}
          </button>
        ))}
      </div>
      <div className="relative mx-auto" style={{ width: WIDTH, height: HEIGHT }}>
        <Figure />
        {tab === "measure" &&
          GUIDES.map((original) => {
            const guide = localizedGuide(original, lang);
            const status = statuses[guide.signal];
            return (
              <button
                key={guide.signal}
                type="button"
                data-indicator={guide.signal}
                aria-pressed={open === guide.signal}
                aria-label={t("guides.twin.openGuide", { label: guide.label, status: status.toLowerCase() })}
                title={guide.label}
                onClick={() => onOpen(guide.signal)}
                // The figure is drawn with a front orthographic camera, so a site maps straight to the box.
                style={place(SITE[guide.signal])}
                className={`absolute h-4 w-4 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 ${DOT[status]} ${open === guide.signal ? "ring-2 ring-shell" : ""} hover:ring-2 hover:ring-shell focus-visible:ring-2 focus-visible:ring-shell`}
              />
            );
          })}
        {tab === "health" &&
          HEALTH_POINTS.map((point) => (
            <button
              key={point.id}
              type="button"
              data-health-point={point.id}
              aria-pressed={healthOpen === point.id}
              aria-label={t("guides.twin.openHealth", { label: healthText(point.label, lang) })}
              title={healthText(point.label, lang)}
              onClick={() => onOpenHealth(point.id)}
              style={place(point.site)}
              className={`absolute h-4 w-4 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-orbit bg-orbit/70 ${healthOpen === point.id ? "ring-2 ring-shell" : ""} hover:ring-2 hover:ring-shell focus-visible:ring-2 focus-visible:ring-shell`}
            />
          ))}
      </div>
    </HudPanel>
  );
}
