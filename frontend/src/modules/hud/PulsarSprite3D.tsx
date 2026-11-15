"use client";

import { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { createRenderer, releaseRenderer } from "@/modules/hud/glRenderer";

export type Mood = "idle" | "talk" | "alert";

/** Internal render size. The canvas is shown at twice this with nearest-neighbour, which gives the pixel-art look. */
const PX = 96;

type V3 = [number, number, number];

function part(geo: THREE.BufferGeometry, mat: THREE.Material, pos: V3, scale: V3 = [1, 1, 1], rot: V3 = [0, 0, 0]) {
  const m = new THREE.Mesh(geo, mat);
  m.position.set(...pos);
  m.scale.set(...scale);
  m.rotation.set(...rot);
  return m;
}

/** PULSAR rebuilt from primitives after docs/brand/pulsar-mascot.png. */
function buildPulsar() {
  const shell = new THREE.MeshToonMaterial({ color: 0xeef1fb });
  const badge = new THREE.MeshToonMaterial({ color: 0xb9c0de });
  const visor = new THREE.MeshBasicMaterial({ color: 0x070d2a });
  const pulse = new THREE.MeshBasicMaterial({ color: 0x5ef2ec });
  const orbit = new THREE.MeshBasicMaterial({ color: 0x9a8cff });
  const ball = new THREE.SphereGeometry(1, 20, 14);
  const arc = new THREE.TorusGeometry(0.16, 0.055, 6, 12, Math.PI);
  const cuff = new THREE.TorusGeometry(0.15, 0.05, 6, 12);
  const ear = new THREE.CylinderGeometry(0.26, 0.26, 0.16, 16);
  const earRing = new THREE.TorusGeometry(0.19, 0.04, 6, 16);

  const eyes = [part(arc, pulse, [-0.3, 0.26, 1.06]), part(arc, pulse, [0.3, 0.26, 1.06])];
  const mouth = part(new THREE.CircleGeometry(0.13, 12, Math.PI, Math.PI), pulse, [0, 0.04, 1.09]);

  const hand = (pos: V3) => {
    const g = new THREE.Group();
    g.add(part(ball, shell, [0, 0, 0], [0.2, 0.2, 0.2]), part(cuff, pulse, [0, -0.17, 0], [1, 1, 1], [Math.PI / 2, 0, 0]));
    g.position.set(...pos);
    return g;
  };
  const wave = hand([1.38, 0.3, 0.3]);

  const beat = part(new THREE.BoxGeometry(0.3, 0.035, 0.02), pulse, [0.2, -0.45, 0.9]); // heartbeat line on the badge

  const body = new THREE.Group();
  body.add(
    part(ball, shell, [0, 0, 0], [1, 1.08, 0.95]),
    part(ball, visor, [0, 0.18, 0.45], [0.8, 0.62, 0.62]),
    part(ball, shell, [0.12, 1.1, 0], [0.45, 0.13, 0.22], [0, 0, -0.35]), // fin
    part(ear, shell, [-0.98, 0.1, 0.05], [1, 1, 1], [0, 0, Math.PI / 2]),
    part(ear, shell, [0.98, 0.1, 0.05], [1, 1, 1], [0, 0, Math.PI / 2]),
    part(earRing, pulse, [-1.07, 0.1, 0.05], [1, 1, 1], [0, Math.PI / 2, 0]),
    part(earRing, pulse, [1.07, 0.1, 0.05], [1, 1, 1], [0, Math.PI / 2, 0]),
    part(ball, badge, [0.2, -0.45, 0.8], [0.26, 0.13, 0.08]),
    beat,
    ...eyes,
    mouth,
    wave,
    hand([-1.25, -0.55, 0.4]),
  );

  // The ring stays out of `body` so it keeps its tilt while the body turns.
  const ring = new THREE.Group();
  ring.add(part(new THREE.TorusGeometry(1.45, 0.04, 6, 48), orbit, [0, 0, 0]), part(ball, pulse, [1.45, 0, 0], [0.08, 0.08, 0.08]));
  ring.position.y = -0.25;
  ring.rotation.set(Math.PI / 2 + 0.35, 0.2, 0); // front edge dips below the visor, as in the render

  const rig = new THREE.Group();
  rig.add(body, ring);
  return { rig, body, ring, eyes, mouth, wave, beat };
}

/**
 * PULSAR as a real-time 3D model drawn like a sprite: tiny canvas, no antialiasing, ~12 fps.
 * `heading` is the yaw in radians (0 faces the camera); the model eases towards it, so adding 2π makes it spin once.
 */
export function PulsarSprite3D({
  heading = 0,
  mood = "idle",
  bpm,
}: {
  heading?: number;
  mood?: Mood;
  /** Heart rate the chest badge beats to; without one the line stays flat. */
  bpm?: number | null;
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const live = useRef({ heading, mood, bpm });
  live.current = { heading, mood, bpm };
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let renderer: THREE.WebGLRenderer;
    try {
      renderer = createRenderer(canvasRef.current!, false);
    } catch {
      setFailed(true); // no WebGL: fall back to the flat sprite
      return;
    }
    renderer.setPixelRatio(1);
    renderer.setSize(PX, PX, false);

    const scene = new THREE.Scene();
    const key = new THREE.DirectionalLight(0xffffff, 2.2);
    key.position.set(-2, 3, 4);
    scene.add(new THREE.AmbientLight(0xb4a8ff, 1.3), key);
    const camera = new THREE.OrthographicCamera(-1.75, 1.75, 1.75, -1.75, 0.1, 20);
    camera.position.z = 6;
    const { rig, body, ring, eyes, mouth, wave, beat } = buildPulsar();
    scene.add(rig);

    const still = matchMedia("(prefers-reduced-motion: reduce)").matches;
    let raf = 0;
    let last = -Infinity;
    const tick = (ms: number) => {
      raf = requestAnimationFrame(tick);
      if (ms - last < 80) return; // ~12 fps on purpose: it reads as sprite animation
      last = ms;
      const t = still ? 0 : ms / 1000;
      const { heading, mood, bpm } = live.current;
      // A short spike once per heartbeat: the badge line jumps to several times its height, then rests.
      beat.scale.y = bpm ? 1 + 5 * Math.max(0, Math.sin((t * bpm * Math.PI) / 30)) ** 12 : 1;

      body.rotation.y = still ? heading : body.rotation.y + (heading - body.rotation.y) * 0.25;
      rig.position.y = Math.sin(t * 2.2) * 0.07;
      rig.position.x = mood === "alert" ? Math.sin(t * 40) * 0.05 : 0;
      ring.rotation.z = t * 1.6;

      const blink = t % 4 > 3.85;
      for (const eye of eyes) {
        eye.rotation.z = mood === "alert" ? Math.PI : 0; // arches flip into worried eyes
        eye.scale.y = blink ? 0.15 : 1;
      }
      mouth.scale.y = mood === "talk" ? 0.4 + Math.abs(Math.sin(t * 9)) : mood === "alert" ? 0.3 : 1;
      wave.position.y = 0.3 + (mood === "talk" ? Math.sin(t * 8) * 0.14 : Math.sin(t * 2) * 0.04);

      renderer.render(scene, camera);
    };
    raf = requestAnimationFrame(tick);

    return () => {
      cancelAnimationFrame(raf);
      releaseRenderer(renderer);
    };
  }, []);

  if (failed) {
    // eslint-disable-next-line @next/next/no-img-element
    return <img src="/brand/pulsar-pixel.png" alt="PULSAR" width={160} height={122} className="pixelated pulsar-float block h-[122px] w-[160px]" />;
  }
  return <canvas ref={canvasRef} role="img" aria-label="PULSAR" className="pixelated block h-48 w-48" />;
}
