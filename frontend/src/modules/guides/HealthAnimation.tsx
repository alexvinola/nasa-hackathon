"use client";

import { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { BLOOD, ORBIT, PULSE, SHELL, UP, arc, ball, disposeScene, group, lightScene, limb, mk, rbox, ring, rod, standingFigure, type V3 } from "./mannequin";
import type { HealthPoint, HealthTool } from "./healthPoints";

/**
 * The 3D picture of a health point: the clay mannequin with the zone glowing, the tool NASA names for it working on
 * the zone and, for "a un compañero", a second mannequin whose hand reaches the zone. Built from primitives like the
 * measuring guides (./GuideAnimation), lit the same way, 20 fps, and one still frame under reduced motion.
 */
const SIZE = 256;
const STILL_T = 2.5;

type Tool = { part: THREE.Group; tick: (t: number) => void };

/** Each tool is drawn around the origin (the zone) and animated in place. */
function toolFor(kind: HealthTool): Tool {
  switch (kind) {
    case "arrows": {
      // The head turning: two arcs going round it.
      const a = mk(arc, ORBIT, [0, 0, 0], [0.42, 0.42, 0.42], [Math.PI / 2, 0, 0], true);
      const b = mk(arc, ORBIT, [0, 0, 0], [0.42, 0.42, 0.42], [Math.PI / 2, 0, Math.PI], true);
      const part = group(a, b);
      return { part, tick: (t) => (part.rotation.y = t * 1.6) };
    }
    case "probe": {
      // A handheld probe (ultrasound, fundoscope) pressed against the zone, with a beam into the body.
      const probe = group(limb(SHELL, [0, 0, 0.7], [0, 0, 0.14], 0.07, 0.05), mk(ball, PULSE, [0, 0, 0.12], [0.07, 0.07, 0.05], [0, 0, 0], true));
      const beam = mk(ring, PULSE, [0, 0, 0.02], [0.12, 0.12, 0.12], [0, 0, 0], true);
      return {
        part: group(probe, beam),
        tick: (t) => {
          probe.position.z = 0.05 * Math.sin(t * 3);
          beam.scale.setScalar(0.12 + 0.22 * ((t * 1.1) % 1));
        },
      };
    }
    case "oxygen": {
      // A tank with a hose to the chest and the chest breathing.
      const tank = mk(rod, SHELL, [0.7, -0.1, 0.1], [0.12, 0.55, 0.12]);
      const hose = limb(ORBIT, [0.7, 0.2, 0.1], [0.12, 0.05, 0.3], 0.03, 0.03, true);
      const lung = mk(ring, PULSE, [0, 0, 0.1], [0.2, 0.2, 0.2], [0, 0, 0], true);
      return { part: group(tank, hose, lung), tick: (t) => lung.scale.setScalar(0.2 + 0.06 * Math.sin(t * 2.2)) };
    }
    case "pack": {
      // A food pack within reach of the belly.
      const pack = rbox(SHELL, [0, 0, 0.5], [0.4, 0.55, 0.1], 0.05, [0.2, 0.3, 0]);
      const spoon = limb(BLOOD, [0.28, 0.2, 0.6], [0.05, 0.05, 0.4], 0.025, 0.04, true);
      return {
        part: group(pack, spoon),
        tick: (t) => {
          pack.position.y = 0.04 * Math.sin(t * 2);
          spoon.position.y = 0.03 * Math.sin(t * 2 + 1);
        },
      };
    }
    case "swab": {
      // A swab going over the skin and a sample tube.
      const swab = group(limb(SHELL, [0.5, 0.3, 0.6], [0.05, 0.02, 0.1], 0.025, 0.02), mk(ball, BLOOD, [0.05, 0.02, 0.1], [0.05, 0.05, 0.05], [0, 0, 0], true));
      const tube = mk(rod, ORBIT, [0.55, -0.3, 0.3], [0.07, 0.3, 0.07]);
      return { part: group(swab, tube), tick: (t) => (swab.position.x = -0.12 * Math.abs(Math.sin(t * 1.8))) };
    }
    case "band": {
      // A band or compression garment squeezing the limb, pulsing.
      const bands = [0, 0.18, -0.18].map((y) => mk(ring, ORBIT, [0, y, 0], [0.2, 0.2, 0.2], [Math.PI / 2, 0, 0], true));
      return { part: group(...bands), tick: (t) => bands.forEach((b, i) => b.scale.setScalar(0.2 + 0.03 * Math.sin(t * 3 + i))) };
    }
    case "load": {
      // Load going down through the spine and hips, as resistive exercise puts it.
      const arrow = (x: number) => group(limb(PULSE, [x, 0.55, 0.15], [x, 0.12, 0.15], 0.035, 0.035, true), mk(ball, PULSE, [x, 0.1, 0.15], [0.07, 0.07, 0.07], [0, 0, 0], true));
      const arrows = [arrow(-0.18), arrow(0.18)];
      return { part: group(...arrows), tick: (t) => arrows.forEach((a) => (a.position.y = -0.1 * ((t * 1.2) % 1))) };
    }
  }
}

export function HealthAnimation({ point, withMate, label }: { point: HealthPoint; withMate: boolean; label: string }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [failed, setFailed] = useState(false);
  const [still, setStill] = useState(false);

  useEffect(() => {
    const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;
    setStill(reduced);
    let renderer: THREE.WebGLRenderer;
    try {
      renderer = new THREE.WebGLRenderer({ canvas: canvasRef.current!, alpha: true, antialias: true });
    } catch {
      setFailed(true); // no WebGL: the lists beside it still carry the guide
      return;
    }
    renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
    renderer.setSize(SIZE, SIZE, false);
    renderer.toneMapping = THREE.NeutralToneMapping;
    const scene = new THREE.Scene();
    lightScene(scene, false);

    const site = new THREE.Vector3(...point.site);
    const body = standingFigure();
    scene.add(body);
    // The zone: a glowing ball and a ripple, with the tool on it.
    const glow = mk(ball, PULSE, point.site, [0.1, 0.1, 0.1], [0, 0, 0], true);
    const ripple = mk(ring, PULSE, point.site, [0.2, 0.2, 0.2], [0, 0, 0], true);
    const { part, tick } = toolFor(point.tool);
    part.position.copy(site);
    scene.add(glow, ripple, part);

    // The helper: a second mannequin beside the first, one arm reaching the zone.
    let reach: THREE.Group | null = null;
    if (withMate) {
      const helper = standingFigure();
      helper.position.set(-1.3, 0, 0.5);
      helper.rotation.y = 0.5;
      scene.add(helper);
      reach = limb(PULSE, [-0.95, 0.45, 0.55], point.site, 0.06, 0.045, true);
      scene.add(reach);
    }

    const camera = new THREE.PerspectiveCamera(27, 1, 0.1, 40);
    const target = withMate ? site.clone().add(new THREE.Vector3(-0.55, 0, 0.2)) : site;
    const distance = withMate ? 7.5 : 3.4;
    const view = new THREE.Vector3(0.25, 0.12, 1).setLength(distance);
    let raf = 0;
    let last = -Infinity;
    const frame = (ms: number) => {
      raf = requestAnimationFrame(frame);
      if (ms - last < 50) return; // 20 fps: leaves a CPU-only laptop room for the HUD
      last = ms;
      const t = reduced ? STILL_T : ms / 1000;
      tick(t);
      ripple.scale.setScalar(0.12 + 0.2 * ((t * 1.1) % 1));
      glow.scale.setScalar(0.09 + 0.025 * Math.sin(t * 4));
      if (reach) reach.scale.set(1, 1 + 0.03 * Math.sin(t * 3), 1);
      camera.position.copy(target).add(view.clone().applyAxisAngle(UP, reduced ? 0 : Math.sin(t * 0.5) * 0.35));
      camera.lookAt(target);
      renderer.render(scene, camera);
    };
    raf = requestAnimationFrame(frame);
    return () => {
      cancelAnimationFrame(raf);
      disposeScene(scene);
      renderer.dispose();
    };
  }, [point, withMate]);

  return (
    <div data-health-animation data-motion={still ? "still" : "loop"} className="h-64 w-64 shrink-0 border border-pulse/30 bg-space-lift/60">
      {failed ? (
        <p className="grid h-full place-items-center p-3 text-center text-xs text-orbit">LA ANIMACIÓN NECESITA WEBGL · SIGUE LOS PASOS</p>
      ) : (
        <canvas ref={canvasRef} role="img" aria-label={`Cómo actuar: ${label}`} className="block h-full w-full" />
      )}
    </div>
  );
}
