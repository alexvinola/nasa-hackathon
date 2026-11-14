/**
 * The mannequin the guides are drawn with: grey clay with its quad mesh showing, like a modelling reference figure.
 * Everything is built here from three.js primitives; no model file is loaded (the demo is offline and the material
 * must be ours).
 */
import * as THREE from "three";
import { RoundedBoxGeometry } from "three/addons/geometries/RoundedBoxGeometry.js";

export const SKIN = 0xc9cdd8; // the mannequin's clay
export const SHELL = 0xeef1fb;
export const VISOR = 0x070d2a;
export const PULSE = 0x5ef2ec;
export const ORBIT = 0x9a8cff;
export const BLOOD = 0xff5a6e;

export type V3 = [number, number, number];

export const ball = new THREE.SphereGeometry(1, 24, 16);
export const rod = new THREE.CylinderGeometry(1, 1, 1, 24, 4); // scale [radius, length, radius]
export const ring = new THREE.TorusGeometry(1, 0.08, 12, 64);
export const arc = new THREE.TorusGeometry(1, 0.2, 12, 32, Math.PI);
export const UP = new THREE.Vector3(0, 1, 0);

const WIRE = new THREE.LineBasicMaterial({ color: 0x4a5275, transparent: true, opacity: 0.55 });
const wires = new WeakMap<THREE.BufferGeometry, THREE.BufferGeometry>();

/** The quad grid of a geometry: every triangle's edges except its longest, which is the diagonal of its quad. */
function quadWire(geometry: THREE.BufferGeometry) {
  const cached = wires.get(geometry);
  if (cached) return cached;
  const position = geometry.attributes.position;
  const index = geometry.index!;
  const corner = [new THREE.Vector3(), new THREE.Vector3(), new THREE.Vector3()];
  const points: number[] = [];
  for (let i = 0; i < index.count; i += 3) {
    corner.forEach((v, k) => v.fromBufferAttribute(position, index.getX(i + k)));
    const lengths = corner.map((v, k) => v.distanceTo(corner[(k + 1) % 3]));
    const diagonal = lengths.indexOf(Math.max(...lengths));
    corner.forEach((v, k) => {
      if (k !== diagonal) points.push(v.x, v.y, v.z, corner[(k + 1) % 3].x, corner[(k + 1) % 3].y, corner[(k + 1) % 3].z);
    });
  }
  const wire = new THREE.BufferGeometry().setAttribute("position", new THREE.Float32BufferAttribute(points, 3));
  wires.set(geometry, wire);
  return wire;
}

/**
 * Every mesh gets its own material, so a part can be dimmed without touching the others. `flat` glows unlit.
 * Clay meshes also show their quad mesh.
 */
export function paint<T extends THREE.Mesh>(mesh: T, color: number, flat = false) {
  mesh.material = flat
    ? new THREE.MeshBasicMaterial({ color, side: THREE.DoubleSide })
    : // The offset keeps the mesh lines from fighting the surface they lie on.
      new THREE.MeshStandardMaterial({ color, roughness: color === SKIN ? 0.75 : 0.35, polygonOffset: true, polygonOffsetFactor: 1, polygonOffsetUnits: 1 });
  mesh.castShadow = !flat;
  mesh.receiveShadow = !flat;
  mesh.userData.base = new THREE.Color(color);
  if (color === SKIN && !flat && mesh.geometry.index) mesh.add(new THREE.LineSegments(quadWire(mesh.geometry), WIRE));
  return mesh;
}
export function mk(geo: THREE.BufferGeometry, color: number, pos: V3, scale: V3 = [1, 1, 1], rot: V3 = [0, 0, 0], flat = false) {
  const mesh = paint(new THREE.Mesh(geo), color, flat);
  mesh.position.set(...pos);
  mesh.scale.set(...scale);
  mesh.rotation.set(...rot);
  return mesh;
}
/** A box with rounded edges: devices, palms, tablets. */
export function rbox(color: number, pos: V3, size: V3, radius = 0.05, rot: V3 = [0, 0, 0]) {
  const mesh = paint(new THREE.Mesh(new RoundedBoxGeometry(...size, 4, radius)), color);
  mesh.position.set(...pos);
  mesh.rotation.set(...rot);
  return mesh;
}
export function group(...children: THREE.Object3D[]) {
  const g = new THREE.Group();
  g.add(...children);
  return g;
}
/** A round-ended segment from `from` to `to`, tapering from `r0` to `r1`: arms, fingers, tubes, probes. */
export function limb(color: number, from: V3, to: V3, r0: number, r1 = r0, flat = false) {
  const a = new THREE.Vector3(...from);
  const b = new THREE.Vector3(...to);
  const length = a.distanceTo(b);
  const rings = Math.max(1, Math.round(length / 0.12));
  const g = group(
    paint(new THREE.Mesh(new THREE.CylinderGeometry(r1, r0, length, 16, rings, true)), color, flat),
    mk(ball, color, [0, -length / 2, 0], [r0, r0, r0], [0, 0, 0], flat),
    mk(ball, color, [0, length / 2, 0], [r1, r1, r1], [0, 0, 0], flat),
  );
  g.position.copy(a).add(b).multiplyScalar(0.5);
  g.quaternion.setFromUnitVectors(UP, b.sub(a).normalize());
  return g;
}

/** Half the height the standing figure needs in view, and its width over height. */
export const FIGURE_HALF_HEIGHT = 1.85;
export const FIGURE_ASPECT = 0.5;

/** The whole mannequin standing, facing +z, feet at y = -1.7 and crown at y = 1.6. */
export function standingFigure() {
  const profile: [number, number][] = [
    [0.001, -0.34], [0.2, -0.33], [0.31, -0.22], [0.34, -0.08], [0.32, 0.08], [0.27, 0.3], [0.3, 0.5],
    [0.36, 0.7], [0.39, 0.86], [0.37, 0.96], [0.24, 1.03], [0.12, 1.07], [0.1, 1.13],
  ];
  const torso = paint(new THREE.Mesh(new THREE.LatheGeometry(profile.map(([x, y]) => new THREE.Vector2(x, y)), 20)), SKIN);
  torso.scale.z = 0.6;
  const side = (s: 1 | -1) => [
    mk(ball, SKIN, [0.43 * s, 0.93, 0], [0.13, 0.13, 0.13]),
    limb(SKIN, [0.43 * s, 0.93, 0], [0.56 * s, 0.3, 0], 0.115, 0.085),
    limb(SKIN, [0.56 * s, 0.3, 0], [0.62 * s, -0.25, 0.05], 0.085, 0.055),
    limb(SKIN, [0.62 * s, -0.25, 0.05], [0.63 * s, -0.5, 0.09], 0.06, 0.04),
    limb(SKIN, [0.17 * s, -0.25, 0], [0.19 * s, -0.98, 0.02], 0.16, 0.105),
    limb(SKIN, [0.19 * s, -0.98, 0.02], [0.2 * s, -1.6, 0], 0.105, 0.065),
    mk(ball, SKIN, [0.2 * s, -1.65, 0.1], [0.09, 0.06, 0.2]),
  ];
  return group(torso, limb(SKIN, [0, 1.08, 0], [0, 1.2, 0], 0.1), mk(ball, SKIN, [0, 1.38, 0.02], [0.17, 0.23, 0.2]), ...side(1), ...side(-1));
}

/** Where on the standing figure each instrument is used. The head carries three, so they sit around it. */
export const SITE: Record<string, V3> = {
  "selfReport.sleepHoursLast24h": [-0.22, 1.6, 0.2], // head
  "selfReport.mood": [0.24, 1.46, 0.2], // head
  "selfReport.bodyTempC": [0, 1.22, 0.2], // mouth
  "selfReport.bloodPressure": [-0.5, 0.62, 0.12], // upper arm
  "biometrics.heartRateBpm": [0.62, -0.22, 0.12], // wrist
  "selfReport.glucoseMgDl": [-0.63, -0.52, 0.14], // fingertip
};

/** Sky light plus key, fill and a rim in the HUD's cyan. The key casts the shadows when `shadows` is on. */
export function lightScene(scene: THREE.Scene, shadows: boolean) {
  const key = new THREE.DirectionalLight(0xffffff, 2.2);
  key.position.set(-3, 6, 4);
  if (shadows) {
    key.castShadow = true;
    key.shadow.mapSize.set(512, 512);
    key.shadow.bias = -0.0005;
    key.shadow.radius = 4;
    Object.assign(key.shadow.camera, { left: -3, right: 3, top: 3, bottom: -3, near: 0.5, far: 20 });
  }
  const fill = new THREE.DirectionalLight(0xb4a8ff, 0.5);
  fill.position.set(5, 3, 5);
  const rim = new THREE.DirectionalLight(PULSE, 1.2);
  rim.position.set(4, 5, -6);
  scene.add(new THREE.HemisphereLight(0xe6ecff, 0x2a3470, 1.5), key, fill, rim);
}

/** Frees the materials of a scene that is going away; the geometries are shared or tiny and re-upload on reuse. */
export function disposeScene(scene: THREE.Scene) {
  scene.traverse((node) => {
    const mesh = node as THREE.Mesh<THREE.BufferGeometry, THREE.Material>;
    if (mesh.isMesh) mesh.material.dispose();
  });
}
