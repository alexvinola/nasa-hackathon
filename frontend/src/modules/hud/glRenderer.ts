import * as THREE from "three";

// The renderer that last took each canvas, so a release that races with a remount (React StrictMode in dev) leaves it alone.
const owner = new WeakMap<HTMLCanvasElement, THREE.WebGLRenderer>();

/** A renderer on `canvas`. Pair it with `releaseRenderer`: `renderer.dispose()` alone keeps the WebGL context alive. */
export function createRenderer(canvas: HTMLCanvasElement, antialias: boolean) {
  const renderer = new THREE.WebGLRenderer({ canvas, alpha: true, antialias });
  owner.set(canvas, renderer);
  return renderer;
}

/**
 * Frees the renderer's WebGL context. Browsers allow about 16 at once and, past that, drop the oldest with "Too many
 * active WebGL contexts": the HUD opens and closes many 3D views, so unreleased contexts made the others go blank.
 */
export function releaseRenderer(renderer: THREE.WebGLRenderer) {
  const canvas = renderer.domElement;
  renderer.dispose();
  // Deferred: a remount in the same tick reuses this canvas and its context, and must keep them.
  setTimeout(() => {
    if (owner.get(canvas) !== renderer) return;
    renderer.forceContextLoss();
    owner.delete(canvas);
  });
}
