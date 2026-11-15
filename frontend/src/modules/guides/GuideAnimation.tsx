"use client";

import { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { useT } from "@/i18n";
import { BLOOD, ORBIT, PULSE, SHELL, SITE, SKIN, UP, VISOR, arc, ball, disposeScene, group, lightScene, limb, mk, ring, rbox, rod, standingFigure, type V3 } from "./mannequin";

/**
 * Unlike the mascot these are instructions, so they are drawn as smooth, lit 3D, not as pixel art: the clay
 * mannequin of ./mannequin with its mesh showing, three-point lighting, soft shadows, a perspective camera. Each
 * loop opens on the whole body with the place the instrument goes, then moves in to how it is used. Kept cheap on
 * purpose (no generated environment, no layered materials): the demo laptop may render without a GPU.
 */
const SIZE = 256; // CSS pixels
const STILL_T = 2.5; // the frame shown under prefers-reduced-motion

const LOOP_S = 10; // one loop: the whole body first, then the close-up
const INTRO_S = 2.4;
const EYE_DISTANCE = 8;

type Built = {
  parts: Record<string, THREE.Group>;
  tick: (t: number) => void;
  /** Direction the camera looks from; scaled to EYE_DISTANCE. */
  camera?: V3;
  /** Height of the surface the scene rests on, which catches the shadows; none for a floating bust. */
  floor?: number;
};

const clamp = (value: number) => Math.min(1, Math.max(0, value));

/**
 * A forearm and hand lying palm up along +x, wrist at the origin, thumb towards +z. Each finger has two segments
 * with a natural curl; `pointing` keeps the index straight and folds the others into the palm.
 */
export function forearmAndHand(pointing = false, forearm = 2.3) {
  const fingers = [0.2, 0.07, -0.06, -0.19].flatMap((z, i) => {
    const length = [0.5, 0.56, 0.52, 0.4][i];
    const r = [0.06, 0.062, 0.058, 0.05][i];
    const folded = pointing && i > 0;
    const knuckle: V3 = [0.5, 0, z];
    const middle: V3 = folded ? [0.5 + 0.3 * length, 0.12, z] : [0.5 + 0.55 * length, pointing ? 0 : 0.04, z];
    const tip: V3 = folded ? [0.5 + 0.1 * length, 0.26, z] : [0.5 + length, pointing ? 0 : 0.12, z];
    return [limb(SKIN, knuckle, middle, r, r * 0.92), limb(SKIN, middle, tip, r * 0.92, r * 0.8)];
  });
  return group(
    limb(SKIN, [-forearm, 0, 0], [-0.02, 0, 0], 0.3, 0.17),
    mk(ball, SKIN, [0.27, 0, 0], [0.3, 0.095, 0.29]),
    mk(ball, SKIN, [0.2, 0.04, 0.2], [0.17, 0.09, 0.13]), // the pad at the base of the thumb
    ...fingers,
    limb(SKIN, [0.12, 0, 0.27], [0.36, 0.03, 0.46], 0.075, 0.065),
    limb(SKIN, [0.36, 0.03, 0.46], [0.56, 0.07, 0.5], 0.065, 0.055),
  );
}
/** The mannequin's head and shoulders facing the camera, with a nose and eyes (open, or closed arcs). */
export function bust(closedEyes = false) {
  const eye = (x: number) =>
    closedEyes ? mk(arc, VISOR, [x, 0.14, 0.8], [0.1, 0.1, 0.1], [0, 0, Math.PI], true) : mk(ball, VISOR, [x, 0.17, 0.77], [0.07, 0.09, 0.04], [0, 0, 0], true);
  return group(
    mk(ball, SKIN, [0, 0.1, 0], [0.8, 0.95, 0.85]),
    mk(ball, SKIN, [0, -0.38, 0.1], [0.62, 0.6, 0.66]),
    mk(ball, SKIN, [-0.8, 0.05, 0], [0.09, 0.19, 0.13]),
    mk(ball, SKIN, [0.8, 0.05, 0], [0.09, 0.19, 0.13]),
    limb(SKIN, [0, 0.12, 0.8], [0, -0.14, 0.9], 0.05, 0.09), // nose
    eye(-0.3),
    eye(0.3),
    limb(SKIN, [0, -0.8, -0.05], [0, -1.35, -0.1], 0.3, 0.34),
    limb(SKIN, [-1.05, -1.7, -0.15], [1.05, -1.7, -0.15], 0.42),
  );
}

/** Forearm palm up, two fingers of the other hand on the thumb side of the wrist, the beat and a timer. */
function pulse(): Built {
  const arm = forearmAndHand();
  arm.position.set(0.7, -0.3, 0);
  // The measuring hand comes in from behind: index and middle fingertips on the wrist, below the base of the thumb.
  const fingers = group(
    limb(SKIN, [0.2, 0.42, -0.42], [0.22, -0.08, 0.14], 0.062, 0.05),
    limb(SKIN, [0.2, 0.62, -0.75], [0.2, 0.42, -0.42], 0.066, 0.062),
    limb(SKIN, [0.4, 0.42, -0.42], [0.4, -0.08, 0.14], 0.064, 0.052),
    limb(SKIN, [0.4, 0.62, -0.75], [0.4, 0.42, -0.42], 0.068, 0.064),
    mk(ball, SKIN, [0.34, 0.68, -1], [0.3, 0.1, 0.28], [0.35, 0, 0]),
    limb(SKIN, [0.34, 0.74, -1.2], [-0.3, 0.95, -2.6], 0.18, 0.28),
  );
  const dot = mk(ball, BLOOD, [0.31, -0.1, 0.16], [0.06, 0.06, 0.06], [0, 0, 0], true);
  const wave = mk(ring, BLOOD, [0.31, -0.12, 0.16], [0.1, 0.1, 0.1], [Math.PI / 2, 0, 0], true);
  const sweep = group(limb(PULSE, [0, 0, 0], [0, 0.34, 0], 0.03, 0.03, true));
  sweep.position.set(1.3, 0.75, -0.9);
  return {
    camera: [0.5, 4.2, 4.4],
    floor: -0.62,
    parts: {
      arm,
      fingers,
      beat: group(dot, wave),
      timer: group(
        mk(ring, ORBIT, [1.3, 0.75, -0.9], [0.45, 0.45, 0.45], [0, 0, 0], true),
        mk(ball, ORBIT, [1.3, 0.75, -0.9], [0.05, 0.05, 0.05], [0, 0, 0], true),
        sweep,
      ),
    },
    tick(t) {
      const phase = (t * 1.1) % 1; // one beat
      const b = Math.max(0, Math.sin(phase * Math.PI)) ** 6;
      dot.scale.setScalar(0.06 * (1 + b));
      wave.scale.setScalar(0.1 + 0.32 * phase); // a ripple leaving the pulse point
      fingers.position.y = -0.015 * b;
      sweep.rotation.z = (-t / 6) * Math.PI * 2; // the timer goes round once per loop
    },
  };
}

/** Upper arm with a cuff that inflates, the forearm resting on a surface, and the monitor the cuff plugs into. */
function bloodPressure(): Built {
  const cuff = mk(rod, ORBIT, [-0.9, 0.5, 0], [0.4, 0.72, 0.4]);
  const bar = mk(rod, PULSE, [1.05, 0.5, 0.33], [0.05, 0.5, 0.01], [0, 0, Math.PI / 2], true);
  const lower = forearmAndHand(false, 1.55);
  lower.position.set(0.72, -0.72, 0.5);
  lower.rotation.y = -0.3;
  return {
    floor: -1,
    parts: {
      arm: group(
        mk(ball, SKIN, [-0.9, 1.3, 0], [0.44, 0.4, 0.42]), // shoulder
        limb(SKIN, [-0.9, 1.15, 0], [-0.86, -0.62, 0.05], 0.31, 0.27),
        lower,
      ),
      cuff: group(cuff, rbox(SHELL, [-0.9, 0.5, 0.4], [0.14, 0.5, 0.04], 0.02)),
      monitor: group(
        rbox(SHELL, [1.05, 0.42, 0], [1.05, 0.8, 0.6], 0.09),
        rbox(VISOR, [1.05, 0.5, 0.29], [0.8, 0.44, 0.04], 0.02),
        bar,
        mk(ball, PULSE, [1.4, 0.13, 0.3], [0.06, 0.06, 0.03], [0, 0, 0], true),
        limb(VISOR, [-0.52, 0.3, 0.2], [0.1, 0.05, 0.45], 0.03), // the air hose
        limb(VISOR, [0.1, 0.05, 0.45], [0.55, 0.3, 0.25], 0.03),
      ),
    },
    tick(t) {
      const p = (t % 5) / 5;
      const inflate = p < 0.6 ? p / 0.6 : 1 - (p - 0.6) / 0.4;
      cuff.scale.set(0.4 + 0.07 * inflate, 0.72, 0.4 + 0.07 * inflate);
      bar.scale.y = 0.05 + 0.6 * inflate;
    },
  };
}

/** A pointing hand, the lancet that pricks the side of the fingertip, the drop, and the meter's strip reaching it. */
function glucose(): Built {
  const pointing = forearmAndHand(true, 1.5);
  pointing.position.set(-1, -0.2, 0);
  const lancet = group(limb(ORBIT, [-0.06, 0.95, 0.2], [-0.06, 0.25, 0.2], 0.1, 0.085), limb(SHELL, [-0.06, 0.14, 0.2], [-0.06, 0.03, 0.2], 0.015), mk(ring, SHELL, [-0.06, 0.7, 0.2], [0.11, 0.11, 0.11], [Math.PI / 2, 0, 0]));
  const drop = mk(ball, BLOOD, [-0.02, -0.11, 0.2], [0.06, 0.06, 0.06]);
  const reading = rbox(PULSE, [1.5, -0.02, 0.2], [0.32, 0.02, 0.16], 0.008);
  (reading.material as THREE.MeshStandardMaterial).emissive.set(PULSE);
  const meter = group(
    rbox(SHELL, [1.45, -0.14, 0.2], [1, 0.2, 0.66], 0.08),
    rbox(VISOR, [1.5, -0.035, 0.2], [0.58, 0.02, 0.4], 0.008),
    reading,
    rbox(PULSE, [0.74, -0.14, 0.2], [0.5, 0.03, 0.15], 0.01), // the test strip
  );
  return {
    camera: [0.5, 4.2, 4.4],
    floor: -0.52,
    parts: { hand: pointing, lancet, drop: group(drop), meter },
    tick(t) {
      const s = t % 6;
      lancet.position.y = s < 0.5 ? -0.14 * Math.sin((s / 0.5) * Math.PI) : 0.15 * clamp(s - 0.5); // jab, then lift away
      drop.scale.setScalar(Math.max(0.001, 0.06 * clamp(s - 0.5)));
      meter.position.x = -0.5 * clamp(s - 2); // the strip reaches the drop between seconds 2 and 3
      reading.visible = s > 3.5;
    },
  };
}

/** A bust with the probe under the tongue and the lips closed on it; the display blinks when it beeps. */
function temperature(): Built {
  const screen = mk(ball, VISOR, [0.98, -0.83, 1.5], [0.14, 0.08, 0.02], [0, 0, 0], true);
  const probe = group(
    limb(SHELL, [0.04, -0.52, 0.7], [0.8, -0.76, 1.3], 0.035, 0.06),
    rbox(SHELL, [0.98, -0.82, 1.42], [0.5, 0.26, 0.14], 0.06, [0, 0.5, -0.25]),
  );
  return {
    camera: [1.6, 0.6, 6],
    parts: {
      head: group(bust(), limb(VISOR, [-0.15, -0.52, 0.72], [0.15, -0.52, 0.72], 0.035)), // closed lips
      thermometer: probe,
      display: group(screen),
    },
    tick(t) {
      const beep = t % 4 > 3 && Math.floor(t * 6) % 2 === 0;
      screen.userData.base.set(beep ? PULSE : VISOR);
    },
  };
}

/** A sleeping head, a clock going round the last 24 hours and the log the total goes into. */
function sleep(): Built {
  const zs = [0, 1, 2].map((i) => mk(ring, PULSE, [0.05 + 0.24 * i, 1 + 0.28 * i, 0.4], [0.07 + 0.03 * i, 0.07 + 0.03 * i, 0.07], [0, 0, 0], true));
  const sleeper = bust(true);
  sleeper.position.set(-0.75, -0.1, 0);
  sleeper.rotation.z = 0.3;
  sleeper.scale.setScalar(0.8);
  const hour = group(limb(PULSE, [0, 0, 0], [0, 0.36, 0], 0.03, 0.03, true));
  hour.position.set(1.1, 0.6, 0);
  const ticks = [...Array(12).keys()].map((i) =>
    mk(ball, ORBIT, [1.1 + 0.5 * Math.sin((i * Math.PI) / 6), 0.6 + 0.5 * Math.cos((i * Math.PI) / 6), 0], i % 3 ? [0.025, 0.025, 0.025] : [0.05, 0.05, 0.05], [0, 0, 0], true),
  );
  const bar = mk(rod, PULSE, [1.1, -0.95, 0.27], [0.06, 0.7, 0.01], [0, 0, Math.PI / 2], true);
  return {
    parts: {
      head: group(sleeper, ...zs),
      clock: group(mk(ring, ORBIT, [1.1, 0.6, 0], [0.58, 0.58, 0.58], [0, 0, 0], true), ...ticks, hour),
      log: group(rbox(SHELL, [1.1, -0.95, 0.15], [1.1, 0.62, 0.12], 0.05), rbox(VISOR, [1.1, -0.95, 0.21], [0.92, 0.44, 0.03], 0.01), bar),
    },
    tick(t) {
      zs.forEach((z, i) => (z.position.y = 1 + 0.28 * i + 0.05 * Math.sin(t * 2 + i)));
      hour.rotation.z = (-t / 6) * Math.PI * 2;
      bar.scale.y = 0.1 + 0.6 * ((t % 6) / 6);
    },
  };
}

/** A face whose mouth follows the number picked on a five-step scale. */
function mood(): Built {
  const mouth = mk(arc, VISOR, [0, -0.5, 0.74], [0.24, 0.24, 0.2], [0, 0, Math.PI], true);
  const face = group(bust(), mouth);
  face.position.y = 0.55;
  face.scale.setScalar(0.82);
  const selector = mk(ring, PULSE, [-1, -1.45, 0.25], [0.2, 0.2, 0.2], [0, 0, 0], true);
  return {
    parts: {
      face,
      scale: group(...[0, 1, 2, 3, 4].map((i) => rbox(SHELL, [-1 + 0.5 * i, -1.45, 0.2], [0.24, 0.24, 0.1], 0.04)), selector),
    },
    tick(t) {
      const level = Math.floor(t / 1.2) % 5; // 0 is the lowest mood, 4 the best
      selector.position.x = -1 + 0.5 * level;
      mouth.scale.y = 0.24 * ((level - 2) / 2) || 0.015; // negative flips the smile into a frown
    },
  };
}

const SCENES: Record<string, () => Built> = {
  "biometrics.heartRateBpm": pulse,
  "selfReport.bloodPressure": bloodPressure,
  "selfReport.glucoseMgDl": glucose,
  "selfReport.bodyTempC": temperature,
  "selfReport.sleepHoursLast24h": sleep,
  "selfReport.mood": mood,
};

/**
 * A short looping 3D picture of how one measurement is taken. `focus` names the part the current how-step is
 * about; the rest of the scene is dimmed.
 */
export function GuideAnimation({ signal, focus, label }: { signal: string; focus: string; label: string }) {
  const t = useT();
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const boxRef = useRef<HTMLDivElement>(null);
  const focusNow = useRef(focus);
  focusNow.current = focus;
  const [failed, setFailed] = useState(false);
  const [still, setStill] = useState(false);

  useEffect(() => {
    const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;
    setStill(reduced);
    const build = SCENES[signal];
    let renderer: THREE.WebGLRenderer;
    try {
      if (!build) throw new Error(`no animation for ${signal}`);
      renderer = new THREE.WebGLRenderer({ canvas: canvasRef.current!, alpha: true, antialias: true });
    } catch {
      setFailed(true); // no WebGL: the numbered steps still carry the guide
      return;
    }
    renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
    renderer.setSize(SIZE, SIZE, false);
    renderer.toneMapping = THREE.NeutralToneMapping;
    renderer.shadowMap.enabled = true;

    const scene = new THREE.Scene();
    lightScene(scene, true);

    const { parts, tick, camera: eye = [1.2, 1.4, 6], floor } = build();
    scene.add(...Object.values(parts));
    let surface: THREE.Mesh | null = null;
    if (floor != null) {
      surface = new THREE.Mesh(new THREE.PlaneGeometry(12, 12), new THREE.ShadowMaterial({ opacity: 0.4 }));
      surface.rotation.x = -Math.PI / 2;
      surface.position.y = floor;
      surface.receiveShadow = true;
      scene.add(surface);
    }
    // The opening shot: the whole mannequin, with a beacon where this instrument is used.
    const site = new THREE.Vector3(...(SITE[signal] ?? [0, 0, 0]));
    const beacon = group(mk(ball, PULSE, [0, 0, 0], [0.06, 0.06, 0.06], [0, 0, 0], true), mk(ring, PULSE, [0, 0, 0], [0.2, 0.2, 0.2], [0, 0, 0], true));
    beacon.position.copy(site);
    const body = group(standingFigure(), beacon);
    scene.add(body);
    const closeUp = Object.values(parts);
    const camera = new THREE.PerspectiveCamera(27, 1, 0.1, 40);
    const home = new THREE.Vector3(...eye).setLength(EYE_DISTANCE);
    const front = new THREE.Vector3(0.8, 0.3, EYE_DISTANCE);
    const started = performance.now();

    let raf = 0;
    let last = -Infinity;
    const frame = (ms: number) => {
      raf = requestAnimationFrame(frame);
      if (ms - last < 50) return; // 20 fps: smooth enough to read, and it leaves a CPU-only laptop room for the HUD
      last = ms;
      const t = reduced ? STILL_T : ms / 1000;
      tick(t);
      // Under reduced motion there is no opening shot: the close-up frame is the picture.
      const intro = !reduced && ((ms - started) / 1000) % LOOP_S < INTRO_S;
      body.visible = intro;
      if (boxRef.current) boxRef.current.dataset.shot = intro ? "body" : "close-up"; // which shot is on screen
      for (const part of closeUp) part.visible = !intro;
      if (surface) surface.visible = !intro;
      beacon.children[1].scale.setScalar(0.12 + 0.2 * ((t * 1.2) % 1));
      // A slow swing around the scene, so its depth reads; none under reduced motion.
      camera.position.copy(intro ? front : home).applyAxisAngle(UP, reduced ? 0 : Math.sin(t * 0.5) * 0.3);
      camera.lookAt(0, 0, 0);
      for (const [name, part] of Object.entries(parts)) {
        const dim = name === focusNow.current || !(focusNow.current in parts) ? 1 : 0.4;
        part.traverse((node) => {
          const mesh = node as THREE.Mesh<THREE.BufferGeometry, THREE.MeshBasicMaterial>;
          if (mesh.isMesh) mesh.material.color.copy(mesh.userData.base).multiplyScalar(dim);
        });
      }
      renderer.render(scene, camera);
    };
    raf = requestAnimationFrame(frame);

    return () => {
      cancelAnimationFrame(raf);
      disposeScene(scene);
      renderer.dispose();
    };
  }, [signal]);

  return (
    <div ref={boxRef} data-guide-animation data-focus={focus} data-motion={still ? "still" : "loop"} className="h-64 w-64 shrink-0 border border-pulse/30 bg-space-lift/60">
      {failed ? (
        <p className="grid h-full place-items-center p-3 text-center text-xs text-orbit">LA ANIMACIÓN NECESITA WEBGL · SIGUE LOS PASOS</p>
      ) : (
        <canvas ref={canvasRef} role="img" aria-label={t("guides.anim.aria", { label })} className="block h-full w-full" />
      )}
    </div>
  );
}
