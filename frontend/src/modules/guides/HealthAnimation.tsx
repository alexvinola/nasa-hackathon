"use client";

import { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { useT } from "@/i18n";
import { BLOOD, ORBIT, PULSE, SHELL, SKIN, UP, VISOR, ball, disposeScene, group, lightScene, limb, mk, rbox, ring, rod, standingFigure, type V3 } from "./mannequin";
import { bust, forearmAndHand } from "./GuideAnimation";
import type { HealthPoint } from "./healthPoints";

/**
 * The 3D picture of a health point, shot like the measuring guides (./GuideAnimation): each loop opens on the whole
 * mannequin with a beacon on the zone, then moves in on that part of the body (the part is drawn, dimmed, with the
 * action bright on top of it): a hand holding the tool, arrows and rings showing which way it works. For "a un
 * compañero" the hand belongs to a second mannequin standing beside. The close-up is divided into one phase per step
 * of the list beside it and reports the phase, so the list can light the matching step. 20 fps, no environment maps,
 * one still close-up under reduced motion. The scene is chosen by the point id (each zone has its own anatomy).
 */
const SIZE = 256;
const STILL_T = 2.5;
const LOOP_S = 10;
const INTRO_S = 2.4;
const EYE_DISTANCE = 8;
const FOOD = 0xffc15e;

const cone = new THREE.ConeGeometry(1, 1, 16);
const sweep = new THREE.TorusGeometry(1, 0.035, 8, 40, Math.PI); // a thin half circle: the body of a turning arrow
const v = (p: V3) => new THREE.Vector3(...p);
const lerp3 = (a: V3, b: V3, u: number): V3 => [a[0] + (b[0] - a[0]) * u, a[1] + (b[1] - a[1]) * u, a[2] + (b[2] - a[2]) * u];
const along = (points: V3[], u: number): V3 => {
  const s = u * (points.length - 1);
  const i = Math.min(points.length - 2, Math.floor(s));
  return lerp3(points[i], points[i + 1], s - i);
};
const dim = (node: THREE.Object3D, k: number) =>
  node.traverse((n) => {
    const m = n as THREE.Mesh<THREE.BufferGeometry, THREE.MeshStandardMaterial>;
    if (m.isMesh) m.material.color.multiplyScalar(k);
  });

type Built = {
  /** The body part itself, drawn dimmed. */
  anatomy: THREE.Group;
  /** Tool, hand and arrows, drawn bright. */
  action: THREE.Group;
  /** Where the glow and the ripples go. */
  zone: V3;
  look: V3;
  /** Direction the camera looks from. */
  eye: V3;
  dist?: number;
  /** Where the helper's bust stands (mate only), so the camera can include it. */
  helper?: V3;
  tick: (t: number) => void;
};

/** A flat arrow from `from` to `to`. */
function arrow(from: V3, to: V3, color = PULSE, r = 0.045) {
  const end = v(to);
  const d = end.clone().sub(v(from));
  const length = d.length();
  d.normalize();
  const head = Math.min(0.24, length * 0.4);
  const tip = mk(cone, color, end.clone().addScaledVector(d, -head / 2).toArray() as V3, [r * 3, head, r * 3], [0, 0, 0], true);
  tip.quaternion.setFromUnitVectors(UP, d);
  return group(limb(color, from, end.clone().addScaledVector(d, -head).toArray() as V3, r, r, true), tip);
}

/**
 * A hand (pointing: its index fingertip lands on `tip`) coming in along `dir`. Alone it is your own hand, with its
 * forearm running off the shot; with `mate` a second mannequin's bust stands at the end of the arm, looking at the zone.
 */
function reach(tip: V3, dir: V3, mate: boolean) {
  const d = v(dir).normalize();
  const q = new THREE.Quaternion().setFromUnitVectors(new THREE.Vector3(1, 0, 0), d);
  const forearm = 1.6;
  const hand = forearmAndHand(true, forearm);
  hand.quaternion.copy(q);
  hand.position.copy(v(tip)).sub(new THREE.Vector3(1, 0, 0.2).applyQuaternion(q));
  const g = group(hand);
  let helper: V3 | undefined;
  if (mate) {
    const person = bust();
    person.scale.setScalar(0.7);
    person.position.copy(hand.position).addScaledVector(d, -(forearm + 0.55)).add(new THREE.Vector3(0, 1, 0));
    person.lookAt(v(tip));
    g.add(person);
    helper = person.position.toArray() as V3;
  }
  return { g, helper };
}

/** The mannequin's chest seen from the front: torso, shoulders, upper arms and neck. */
function torso() {
  const side = (s: 1 | -1) => [mk(ball, SKIN, [1.05 * s, 0.9, 0], [0.3, 0.3, 0.3]), limb(SKIN, [1.05 * s, 0.9, 0], [1.2 * s, -0.7, 0.1], 0.26, 0.2)];
  return group(mk(ball, SKIN, [0, 0, 0], [1, 1.3, 0.62]), limb(SKIN, [0, 1.1, 0], [0, 1.75, 0], 0.26, 0.22), ...side(1), ...side(-1));
}

/** A forearm and hand lying palm up along x, wrist at x = 0.3. */
function armAnatomy() {
  const arm = forearmAndHand(false, 2.2);
  arm.position.set(0.3, 0, 0);
  return arm;
}

/** A handheld probe whose business end is at `tip`, its handle running back along `dir`. */
function probeTool(tip: V3, dir: V3) {
  const d = v(dir).normalize();
  const at = (k: number): V3 => v(tip).addScaledVector(d, k).toArray() as V3;
  const g = group(limb(SHELL, at(0.25), at(1.7), 0.1, 0.07), mk(ball, PULSE, at(0.12), [0.11, 0.11, 0.07], [0, 0, 0], true));
  return { g, d, at };
}

/** The head with two arrows turning round it, a hand steadying it from the side. */
function headScene(mate: boolean): Built {
  const turn = (angle: number) => {
    const inner = group(mk(sweep, ORBIT, [0, 0, 0], [1.25, 1.25, 1.25], [0, 0, 0], true), mk(cone, ORBIT, [-1.25, 0, 0], [0.12, 0.3, 0.12], [0, 0, Math.PI], true));
    inner.rotation.z = angle;
    const tilt = group(inner);
    tilt.rotation.x = Math.PI / 2; // lay the circle flat, round the head
    return tilt;
  };
  const spin = group(turn(0), turn(Math.PI));
  spin.position.y = 0.1;
  const hand = reach([0.9, 0.15, 0.2], [-1, 0.05, -0.15], mate);
  return { anatomy: bust(), action: group(spin, hand.g), zone: [0, 1.0, 0.1], look: [0, -0.2, 0], eye: [0.3, 0.25, 1], helper: hand.helper, tick: (t) => (spin.rotation.y = t * 1.6) };
}

/** The face with a fundoscope in front of one eye and light going into it. */
function eyesScene(mate: boolean): Built {
  const tip: V3 = [-0.3, 0.17, 0.95];
  const probe = probeTool(tip, [0.5, -0.1, 1]);
  const beam = mk(ring, PULSE, tip, [0.1, 0.1, 0.1], [0, 0, 0], true);
  const hand = reach(probe.at(1.2), [-0.8, 0.15, -0.2], mate);
  return {
    anatomy: bust(),
    action: group(probe.g, beam, hand.g),
    zone: [-0.3, 0.17, 0.8],
    look: [0.2, 0, 0.3],
    eye: [0.35, 0.2, 1],
    helper: hand.helper,
    tick(t) {
      probe.g.position.copy(probe.d).multiplyScalar(0.05 * Math.sin(t * 3));
      beam.scale.setScalar(0.06 + 0.2 * ((t * 1.1) % 1));
    },
  };
}

/** The chest with an ultrasound probe pressed on it, its beam and the heartbeat under it. */
function heartScene(mate: boolean): Built {
  const tip: V3 = [0.3, 0.2, 0.6];
  const probe = probeTool(tip, [0.5, -0.2, 1]);
  const beam = mk(ring, PULSE, tip, [0.1, 0.1, 0.1], [0, 0, 0], true);
  const beat = mk(ball, BLOOD, [-0.1, 0.2, 0.62], [0.08, 0.08, 0.08], [0, 0, 0], true);
  const wave = mk(ring, BLOOD, [-0.1, 0.2, 0.62], [0.1, 0.1, 0.1], [0, 0, 0], true);
  const hand = reach(probe.at(1.1), [-0.9, 0.1, -0.3], mate);
  return {
    anatomy: torso(),
    action: group(probe.g, beam, beat, wave, hand.g),
    zone: [0.3, 0.2, 0.6],
    look: [0.1, 0.1, 0],
    eye: [0.3, 0.2, 1],
    helper: hand.helper,
    tick(t) {
      const phase = (t * 1.1) % 1;
      beat.scale.setScalar(0.08 * (1 + Math.max(0, Math.sin(phase * Math.PI)) ** 6));
      wave.scale.setScalar(0.1 + 0.3 * phase);
      probe.g.position.copy(probe.d).multiplyScalar(0.04 * Math.sin(t * 3));
      beam.scale.setScalar(0.08 + 0.22 * ((t * 1.3) % 1));
    },
  };
}

/** A face with an oxygen mask, the hose going to the tank and the oxygen running along it. */
function lungsScene(mate: boolean): Built {
  const path: V3[] = [[1.7, -0.6, 0.3], [1.0, -1.0, 1.0], [0.35, -0.4, 0.95]];
  const flow = [0, 1, 2, 3].map(() => mk(ball, PULSE, path[0], [0.07, 0.07, 0.07], [0, 0, 0], true));
  const valve = mk(ball, PULSE, [0, -0.34, 1.08], [0.07, 0.07, 0.07], [0, 0, 0], true);
  const hand = reach([0.55, -0.3, 0.95], [-1, 0.1, -0.2], mate);
  const chest = mk(ring, PULSE, [0, -1.45, 0.35], [0.2, 0.2, 0.2], [0, 0, 0], true);
  return {
    anatomy: bust(),
    action: group(
      mk(ball, SHELL, [0, -0.3, 0.82], [0.42, 0.34, 0.3]), // the mask
      valve,
      limb(ORBIT, path[2], path[1], 0.06),
      limb(ORBIT, path[1], path[0], 0.06),
      mk(rod, SHELL, [1.7, -0.9, 0.3], [0.28, 0.7, 0.28]),
      mk(ball, ORBIT, [1.7, -0.2, 0.3], [0.2, 0.2, 0.2]),
      ...flow,
      chest,
      hand.g,
    ),
    zone: [0, -1.45, 0.35],
    look: [0.4, -0.4, 0],
    eye: [0.3, 0.2, 1],
    helper: hand.helper,
    tick(t) {
      flow.forEach((f, i) => f.position.set(...along(path, (t * 0.5 + i / 4) % 1)));
      valve.scale.setScalar(0.07 * (1 + 0.5 * Math.max(0, Math.sin(t * 2.2))));
      chest.scale.setScalar(0.2 + 0.12 * Math.max(0, Math.sin(t * 2.2))); // the chest filling
    },
  };
}

/** A face with the mouth open, a food pouch squeezed towards it and the food going in. */
function gutScene(mate: boolean): Built {
  const spout: V3 = [0.66, -0.61, 1.7];
  const mouthAt: V3 = [0.12, -0.5, 0.95];
  const mouth = mk(ball, VISOR, [0, -0.5, 0.76], [0.14, 0.07, 0.04], [0, 0, 0], true);
  const pouch = rbox(SHELL, [0.9, -1.05, 1.7], [0.7, 1, 0.14], 0.06, [0, 0, 0.5]);
  const bites = [0, 1, 2].map(() => mk(ball, FOOD, spout, [0.06, 0.06, 0.06], [0, 0, 0], true));
  const hand = reach([0.95, -1.3, 1.8], [-0.6, 0.6, -0.2], mate);
  return {
    anatomy: bust(),
    action: group(mouth, pouch, limb(SHELL, spout, mouthAt, 0.07), ...bites, hand.g),
    zone: [0, -0.5, 0.8],
    look: [0.3, -0.6, 0.5],
    eye: [0.3, 0.2, 1],
    helper: hand.helper,
    tick(t) {
      pouch.scale.set(1, 1 - 0.08 * Math.max(0, Math.sin(t * 2.4)), 1);
      mouth.scale.set(0.14, 0.03 + 0.06 * Math.max(0, Math.sin(t * 2.4 + 1.2)), 0.04);
      bites.forEach((b, i) => b.position.set(...lerp3(spout, mouthAt, (t * 0.8 + i / 3) % 1)));
    },
  };
}

/** A forearm with a rash, a swab wiping over it and a sample tube waiting. */
function skinScene(mate: boolean): Built {
  const swab = group(limb(SHELL, [0, 1.3, 0.3], [0, 0.3, 0.05], 0.04, 0.03), mk(ball, SHELL, [0, 0.28, 0.05], [0.07, 0.07, 0.07]));
  swab.position.x = -0.6;
  const hand = reach([-0.6, 0.9, 0.25], [-0.6, -0.2, -0.7], mate);
  return {
    anatomy: armAnatomy(),
    action: group(
      mk(ball, BLOOD, [-0.6, 0.2, 0], [0.28, 0.05, 0.22], [0, 0, 0], true), // the rash
      swab,
      mk(rod, SHELL, [1.6, 0.25, 0.9], [0.12, 0.7, 0.12], [0, 0, 0.25]),
      mk(ball, ORBIT, [1.52, 0.93, 0.9], [0.14, 0.1, 0.14]),
      hand.g,
    ),
    zone: [-0.6, 0.2, 0],
    look: [0, 0.2, 0.2],
    eye: [0.3, 1.1, 1],
    helper: hand.helper,
    tick: (t) => (swab.position.x = -0.6 + 0.3 * Math.sin(t * 2.4)),
  };
}

/** A forearm with a band that squeezes it, an arrow on each side showing the squeeze. */
function handsScene(mate: boolean): Built {
  const band = mk(rod, ORBIT, [-0.7, 0, 0], [0.3, 0.55, 0.3], [0, 0, Math.PI / 2]);
  const top = arrow([-0.7, 1, 0], [-0.7, 0.45, 0]);
  const front = arrow([-0.7, 0, 1], [-0.7, 0, 0.45]);
  const under = arrow([-0.7, -1, 0], [-0.7, -0.45, 0]);
  const hand = reach([-0.7, 0.55, 0.6], [-0.3, -0.5, -0.8], mate);
  return {
    anatomy: armAnatomy(),
    action: group(band, top, front, under, hand.g),
    zone: [-0.7, 0, 0],
    look: [0, 0.2, 0.2],
    eye: [0.3, 0.9, 1],
    helper: hand.helper,
    tick(t) {
      const squeeze = 0.5 + 0.5 * Math.sin(t * 3);
      band.scale.set(0.31 - 0.07 * squeeze, 0.55, 0.31 - 0.07 * squeeze);
      top.position.y = -0.12 * squeeze;
      under.position.y = 0.12 * squeeze;
      front.position.z = -0.12 * squeeze;
    },
  };
}

/** A leg with a compression sleeve on the calf that squeezes, and blood arrows going up. */
function legsScene(mate: boolean): Built {
  const sleeve = mk(rod, ORBIT, [0.01, -0.9, 0.02], [0.2, 0.7, 0.2]);
  const up = [-0.45, 0.45].map((x) => arrow([x, -1.5, 0.1], [x, -0.7, 0.1]));
  const hand = reach([0.2, -0.5, 0.2], [-0.9, 0.1, -0.3], mate);
  return {
    anatomy: group(
      limb(SKIN, [0, 1.3, 0], [0.02, -0.2, 0.05], 0.32, 0.22),
      mk(ball, SKIN, [0.02, -0.2, 0.05], [0.22, 0.22, 0.22]),
      limb(SKIN, [0.02, -0.2, 0.05], [0, -1.55, 0], 0.21, 0.13),
      mk(ball, SKIN, [0, -1.7, 0.2], [0.14, 0.1, 0.34]),
    ),
    action: group(sleeve, ...up, hand.g),
    zone: [0.01, -0.9, 0.2],
    look: [0, -0.2, 0],
    eye: [0.5, 0.2, 1],
    helper: hand.helper,
    tick(t) {
      sleeve.scale.set(0.2 + 0.04 * Math.sin(t * 3), 0.7, 0.2 + 0.04 * Math.sin(t * 3));
      up.forEach((a) => (a.position.y = 0.7 * ((t * 0.7) % 1))); // the flow climbing the leg
    },
  };
}

/** The back seen from behind, spine and hips on a platform, load arrows pressing down and the legs pushing up. */
function spineScene(mate: boolean): Built {
  const spine = [...Array(9).keys()].map((i) => {
    const y = 0.9 - i * 0.22;
    return mk(ball, ORBIT, [0, y, -0.62 * Math.sqrt(Math.max(0.05, 1 - (y / 1.3) ** 2)) - 0.02], [0.11, 0.1, 0.09], [0, 0, 0], true);
  });
  const down = [-0.45, 0.45].map((x) => arrow([x, 1.5, -0.75], [x, 0.7, -0.75]));
  const push = [-0.4, 0.4].map((x) => arrow([x, -2.3, 0.1], [x, -1.8, 0.1], ORBIT));
  const hand = reach([0.5, 0.5, -0.5], [-0.8, -0.2, 0.5], mate);
  return {
    anatomy: group(
      torso(),
      mk(ball, SKIN, [0, -1.25, 0], [0.75, 0.4, 0.5]),
      limb(SKIN, [0.3, -1.3, 0], [0.32, -2.35, 0], 0.26, 0.18),
      limb(SKIN, [-0.3, -1.3, 0], [-0.32, -2.35, 0], 0.26, 0.18),
      rbox(SHELL, [0, -2.45, 0], [1.8, 0.1, 1], 0.04),
    ),
    action: group(...spine, ...down, ...push, hand.g),
    zone: [0, -0.3, -0.45],
    look: [0, -0.4, 0],
    eye: [0.4, 0.25, -1],
    dist: 9,
    helper: hand.helper,
    tick(t) {
      spine.forEach((s, i) => s.scale.set(0.11, 0.1, 0.09).multiplyScalar(1 + 0.35 * Math.max(0, Math.sin(t * 3 - i * 0.5)))); // the load travelling down
      down.forEach((a) => (a.position.y = -0.8 * ((t * 0.7) % 1)));
      push.forEach((a) => (a.position.y = 0.15 * Math.sin(t * 3)));
    },
  };
}

const SCENES: Record<string, (mate: boolean) => Built> = {
  head: headScene,
  eyes: eyesScene,
  heart: heartScene,
  lungs: lungsScene,
  gut: gutScene,
  skin: skinScene,
  hands: handsScene,
  spine: spineScene,
  legs: legsScene,
};

/** A flat ring that always faces the camera. */
const billboard = (node: THREE.Object3D, camera: THREE.Camera) => node.quaternion.copy(camera.quaternion);

export function HealthAnimation({ point, withMate, label, steps, onStep }: { point: HealthPoint; withMate: boolean; label: string; steps: number; onStep: (index: number) => void }) {
  const t = useT();
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const boxRef = useRef<HTMLDivElement>(null);
  const stepNow = useRef(onStep);
  stepNow.current = onStep;
  const [failed, setFailed] = useState(false);
  const [still, setStill] = useState(false);

  useEffect(() => {
    const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;
    setStill(reduced);
    const build = SCENES[point.id];
    let renderer: THREE.WebGLRenderer;
    try {
      if (!build) throw new Error(`no animation for ${point.id}`);
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

    // The opening shot: the whole mannequin (and the helper) with a beacon on the zone.
    const site = v(point.site);
    const beacon = group(mk(ball, PULSE, [0, 0, 0], [0.06, 0.06, 0.06], [0, 0, 0], true), mk(ring, PULSE, [0, 0, 0], [0.2, 0.2, 0.2], [0, 0, 0], true));
    beacon.position.copy(site);
    const body = group(standingFigure(), beacon);
    if (withMate) {
      const helper = standingFigure();
      helper.position.set(-1.2, 0, 0.3);
      helper.rotation.y = 0.6;
      body.add(helper, limb(PULSE, [-0.845, 0.93, 0.057], point.site, 0.06, 0.045, true));
    }
    scene.add(body);

    // The close-up: the body part dimmed, the action bright, the glow on the zone and a dot per step.
    const { anatomy, action, zone, look, eye, dist = EYE_DISTANCE, helper, tick } = build(withMate);
    dim(anatomy, 0.6);
    const glow = mk(ball, PULSE, zone, [0.09, 0.09, 0.09], [0, 0, 0], true);
    const ripple = mk(ring, PULSE, zone, [0.2, 0.2, 0.2], [0, 0, 0], true);
    const burst = mk(ring, PULSE, zone, [0.3, 0.3, 0.3], [0, 0, 0], true);
    const dots = [...Array(steps).keys()].map(() => mk(ball, ORBIT, [0, 0, 0], [1, 1, 1], [0, 0, 0], true));
    const markers = group(...dots);
    const closeUp = group(anatomy, action, glow, ripple, burst, markers);
    scene.add(closeUp);

    const camera = new THREE.PerspectiveCamera(27, 1, 0.1, 60);
    // With a helper the close-up pulls back and moves towards it so both bodies are in the shot.
    const closeLook = v(look);
    let closeDist = dist;
    if (helper) {
      closeLook.lerp(v(helper), 0.45);
      closeDist = dist * 1.6;
    }
    const closeEye = v(eye).setLength(closeDist);
    const introLook = new THREE.Vector3(withMate ? -0.55 : 0, 0, 0);
    const introEye = new THREE.Vector3(0.8, 0.3, withMate ? 9.5 : EYE_DISTANCE);
    const offset = new THREE.Vector3();
    const down = new THREE.Vector3();
    const forward = new THREE.Vector3();
    const phaseLength = (LOOP_S - INTRO_S) / steps;
    const started = performance.now();
    let lastPhase = Number.NaN;

    let raf = 0;
    let last = -Infinity;
    const frame = (ms: number) => {
      raf = requestAnimationFrame(frame);
      if (ms - last < 50) return; // 20 fps: leaves a CPU-only laptop room for the HUD
      last = ms;
      const time = reduced ? STILL_T : ms / 1000;
      const cycle = ((ms - started) / 1000) % LOOP_S;
      const intro = !reduced && cycle < INTRO_S;
      const phase = reduced || intro ? -1 : Math.min(steps - 1, Math.floor((cycle - INTRO_S) / phaseLength));
      const progress = phase < 0 ? 1 : ((cycle - INTRO_S) % phaseLength) / phaseLength;
      if (phase !== lastPhase) {
        lastPhase = phase;
        stepNow.current(phase);
      }
      if (boxRef.current) {
        boxRef.current.dataset.shot = intro ? "body" : "close-up";
        boxRef.current.dataset.step = String(phase);
      }
      body.visible = intro;
      closeUp.visible = !intro;
      tick(time);
      glow.scale.setScalar(0.09 + 0.025 * Math.sin(time * 4));
      ripple.scale.setScalar(0.12 + 0.2 * ((time * 1.1) % 1));
      beacon.children[1].scale.setScalar(0.12 + 0.2 * ((time * 1.2) % 1));
      burst.visible = phase >= 0 && progress < 0.4; // a ring leaves the zone each time a new step starts
      burst.scale.setScalar(0.15 + 1.2 * progress);

      // A slow swing around what is in shot, so its depth reads; none under reduced motion.
      const swing = reduced ? 0 : Math.sin(time * 0.5) * 0.3;
      offset.copy(intro ? introEye : closeEye).applyAxisAngle(UP, swing);
      camera.position.copy(intro ? introLook : closeLook).add(offset);
      camera.lookAt(intro ? introLook : closeLook);
      camera.updateMatrixWorld();
      for (const node of [ripple, burst, beacon.children[1]]) billboard(node, camera);

      // The step dots sit at the bottom of the shot, in the camera's plane; the current one is big and bright.
      const depth = closeDist - 3;
      const half = depth * 0.24;
      forward.set(0, 0, -1).applyQuaternion(camera.quaternion);
      down.set(0, -1, 0).applyQuaternion(camera.quaternion);
      markers.position.copy(camera.position).addScaledVector(forward, depth).addScaledVector(down, half * 0.86);
      markers.quaternion.copy(camera.quaternion);
      dots.forEach((dot, i) => {
        const on = i === phase;
        dot.position.set((i - (steps - 1) / 2) * half * 0.16, 0, 0);
        dot.scale.setScalar(half * (on ? 0.055 : 0.03));
        dot.userData.base.set(on ? PULSE : ORBIT);
        (dot.material as THREE.MeshBasicMaterial).color.copy(dot.userData.base);
      });
      renderer.render(scene, camera);
    };
    raf = requestAnimationFrame(frame);
    return () => {
      cancelAnimationFrame(raf);
      disposeScene(scene);
      renderer.dispose();
    };
  }, [point, withMate, steps]);

  return (
    <div ref={boxRef} data-health-animation data-motion={still ? "still" : "loop"} className="h-64 w-64 shrink-0 border border-pulse/30 bg-space-lift/60">
      {failed ? (
        <p className="grid h-full place-items-center p-3 text-center text-xs text-orbit">{t("guides.health.anim.failed")}</p>
      ) : (
        <canvas ref={canvasRef} role="img" aria-label={t("guides.health.anim.aria", { label })} className="block h-full w-full" />
      )}
    </div>
  );
}
