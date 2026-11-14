"use client";

import { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { HudPanel } from "@/modules/hud/HudPanel";
import { GUIDES, type GuideStatus } from "./guides";
import { FIGURE_ASPECT, FIGURE_HALF_HEIGHT, SITE, disposeScene, lightScene, standingFigure } from "./mannequin";

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
      renderer = new THREE.WebGLRenderer({ canvas: canvasRef.current!, alpha: true, antialias: true });
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
      renderer.dispose();
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
}: {
  statuses: Record<string, GuideStatus>;
  /** Signal of the guide currently open, if any. */
  open: string | null;
  onOpen: (signal: string) => void;
}) {
  return (
    <HudPanel title="HOW TO MEASURE" data-twin>
      <div className="relative mx-auto" style={{ width: WIDTH, height: HEIGHT }}>
        <Figure />
        {GUIDES.map((guide) => {
          const [x, y] = SITE[guide.signal];
          const status = statuses[guide.signal];
          return (
            <button
              key={guide.signal}
              type="button"
              data-indicator={guide.signal}
              aria-pressed={open === guide.signal}
              aria-label={`Open the guide: ${guide.label} (${status.toLowerCase()})`}
              title={guide.label}
              onClick={() => onOpen(guide.signal)}
              // The figure is drawn with a front orthographic camera, so a site maps straight to the box.
              style={{
                left: `${((x / (FIGURE_HALF_HEIGHT * FIGURE_ASPECT) + 1) / 2) * 100}%`,
                top: `${((1 - y / FIGURE_HALF_HEIGHT) / 2) * 100}%`,
              }}
              className={`absolute h-4 w-4 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 ${DOT[status]} ${open === guide.signal ? "ring-2 ring-shell" : ""} hover:ring-2 hover:ring-shell focus-visible:ring-2 focus-visible:ring-shell`}
            />
          );
        })}
      </div>
    </HudPanel>
  );
}
