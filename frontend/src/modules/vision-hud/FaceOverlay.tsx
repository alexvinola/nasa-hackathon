"use client";

import { useEffect, useRef, useState, type MutableRefObject, type RefObject } from "react";
import { FaceLandmarker } from "@mediapipe/tasks-vision";
import type { FaceFrame } from "./faceWorker";
import { useAiCheck, type Tally } from "./useAiCheck";

type Connection = { start: number; end: number };

const PULSE = "94, 242, 236"; // brand tokens (app/globals.css) as rgb, for alpha
const ORBIT = "154, 140, 255";
const AMBER = "251, 191, 36";
const BLINK = 0.5;
const MOUTH = 0.35;

// Landmark indices (MediaPipe face mesh): eye outer corners, mouth corner, forehead, nose tip.
const LEFT_EYE_OUTER = 263;
const RIGHT_EYE_OUTER = 33;
const MOUTH_CORNER = 291;
const FOREHEAD = 10;
const NOSE_TIP = 1;

/**
 * MediaPipe's view of the astronaut, drawn over the camera: the 478-point face mesh, eyes and mouth coloured by the
 * blendshape scores the metrics use, head-pose axes, and an AI cross-check
 * badge (Gemma looking at the same frame). The canvas has the video's size and CSS, so the points land on the face.
 */
export function FaceOverlay({ frameRef, videoRef }: { frameRef: MutableRefObject<FaceFrame | null>; videoRef: RefObject<HTMLVideoElement | null> }) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const [show, setShow] = useState(true);
  const fps = useRef({ last: 0, value: 0 });
  const { last, tally, error } = useAiCheck(videoRef, frameRef, show);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key.toLowerCase() === "m" && !(e.target instanceof HTMLInputElement)) setShow((s) => !s);
    };
    addEventListener("keydown", onKey);
    return () => removeEventListener("keydown", onKey);
  }, []);

  useEffect(() => {
    if (!show) return;
    let raf = 0;
    let drawnAt = -1;
    const loop = () => {
      raf = requestAnimationFrame(loop);
      const frame = frameRef.current;
      const el = canvas.current;
      if (!frame || !el || frame.at === drawnAt) return;
      if (drawnAt > 0) fps.current.value = 0.9 * fps.current.value + 0.1 * (1000 / Math.max(1, frame.at - drawnAt));
      drawnAt = frame.at;
      if (el.width !== frame.width || el.height !== frame.height) Object.assign(el, { width: frame.width, height: frame.height });
      draw(el.getContext("2d")!, frame, fps.current.value);
    };
    raf = requestAnimationFrame(loop);
    return () => {
      cancelAnimationFrame(raf);
      canvas.current?.getContext("2d")?.clearRect(0, 0, canvas.current.width, canvas.current.height);
    };
  }, [show, frameRef]);

  return (
    <>
      <canvas ref={canvas} className={`pointer-events-none absolute inset-0 h-full w-full -scale-x-100 object-cover ${show ? "" : "hidden"}`} />
      {/* Stacked above the debug panel (sim-core/DebugPanel), clear of the controls at the bottom of the HUD. */}
      <div data-hud-panel className="absolute bottom-[19rem] left-8 w-64 border border-pulse/30 bg-space/70 p-3 text-xs tracking-[0.12em] text-shell/80 backdrop-blur">
        <div className="flex items-center justify-between text-pulse">
          <span>AI CHECK · GEMMA 4</span>
          <button type="button" onClick={() => setShow((s) => !s)} className="border border-pulse/50 px-2 py-1 text-xs text-pulse">
            MESH {show ? "ON" : "OFF"} (M)
          </button>
        </div>
        {last ? (
          <dl className="mt-2 space-y-1">
            <Row label="EYES" mp={last.claim.eyes} ai={last.ai.eyes} ok={last.agrees.eyes} tally={tally.eyes} />
            <Row label="MOUTH" mp={last.claim.mouth} ai={last.ai.mouth} ok={last.agrees.mouth} tally={tally.mouth} />
            <div className="pt-1 text-shell/40">{last.ai.person ? "FACE CONFIRMED" : "NO FACE SEEN BY AI"} · {Math.round(last.ms)} MS</div>
          </dl>
        ) : (
          <p className="mt-2 text-shell/40">{show ? "FIRST CHECK IN A FEW SECONDS" : "PAUSED WITH THE MESH"}</p>
        )}
        {error && <p className="mt-1 text-red-400">{error}</p>}
        <p className="mt-2 text-[9px] tracking-normal text-shell/40">Evidence only: the rules engine decides.</p>
      </div>
    </>
  );
}

function Row({ label, mp, ai, ok, tally }: { label: string; mp: string; ai: string; ok: boolean | null; tally: Tally }) {
  const mark = ok === null ? "·" : ok ? "✓" : "✗";
  const tone = ok === null ? "text-shell/50" : ok ? "text-emerald-400" : "text-amber-400";
  return (
    <div className="flex justify-between">
      <dt>{label}</dt>
      <dd>
        MP {mp.toUpperCase()} · AI {ai.toUpperCase()} <span className={tone}>{mark}</span>{" "}
        <span className="text-shell/40">{tally.total ? `${tally.agree}/${tally.total}` : ""}</span>
      </dd>
    </div>
  );
}

function draw(ctx: CanvasRenderingContext2D, f: FaceFrame, fps: number) {
  const { width: w, height: h } = f;
  ctx.clearRect(0, 0, w, h);
  const unit = h / 480; // line widths and text scale with the worker's input resolution (640 px wide)
  ctx.lineCap = "round";

  if (!f.face) return;
  const p = f.face;
  const at = (i: number): [number, number] => [p[i * 3] * w, p[i * 3 + 1] * h];

  const lines = (connections: Connection[], color: string, width: number) => {
    ctx.strokeStyle = color;
    ctx.lineWidth = width * unit;
    ctx.beginPath();
    for (const { start, end } of connections) {
      const [x1, y1] = at(start);
      const [x2, y2] = at(end);
      ctx.moveTo(x1, y1);
      ctx.lineTo(x2, y2);
    }
    ctx.stroke();
  };

  lines(FaceLandmarker.FACE_LANDMARKS_TESSELATION, `rgba(${PULSE}, 0.10)`, 0.6);
  ctx.fillStyle = `rgba(${PULSE}, 0.45)`;
  for (let i = 0; i < p.length / 3; i++) {
    const [x, y] = at(i);
    ctx.fillRect(x - 0.7 * unit, y - 0.7 * unit, 1.4 * unit, 1.4 * unit);
  }
  lines(FaceLandmarker.FACE_LANDMARKS_FACE_OVAL, `rgba(${PULSE}, 0.55)`, 1);
  lines(FaceLandmarker.FACE_LANDMARKS_LEFT_EYEBROW, `rgba(${PULSE}, 0.55)`, 1);
  lines(FaceLandmarker.FACE_LANDMARKS_RIGHT_EYEBROW, `rgba(${PULSE}, 0.55)`, 1);
  const eye = (score: number) => (score > BLINK ? `rgba(${AMBER}, 0.95)` : `rgba(${PULSE}, 0.95)`);
  lines(FaceLandmarker.FACE_LANDMARKS_LEFT_EYE, eye(f.eyeLeft), 1.8);
  lines(FaceLandmarker.FACE_LANDMARKS_RIGHT_EYE, eye(f.eyeRight), 1.8);
  lines(FaceLandmarker.FACE_LANDMARKS_LEFT_IRIS, `rgba(${PULSE}, 0.9)`, 1.2);
  lines(FaceLandmarker.FACE_LANDMARKS_RIGHT_IRIS, `rgba(${PULSE}, 0.9)`, 1.2);
  lines(FaceLandmarker.FACE_LANDMARKS_LIPS, f.jaw > MOUTH ? `rgba(${AMBER}, 0.95)` : `rgba(${PULSE}, 0.8)`, 1.4);

  // Callouts point away from the face centre, like an instrument readout.
  const [cx] = at(NOSE_TIP);
  const callout = (i: number, text: string, color: string) => {
    const [x, y] = at(i);
    const dir = Math.sign(x - cx) || 1;
    const ex = x + dir * 46 * unit;
    const ey = y - 18 * unit;
    ctx.strokeStyle = color;
    ctx.lineWidth = 1 * unit;
    ctx.beginPath();
    ctx.moveTo(x, y);
    ctx.lineTo(ex, ey);
    ctx.lineTo(ex + dir * 14 * unit, ey);
    ctx.stroke();
    label(ctx, ex + dir * 18 * unit, ey + 4 * unit, text, color, unit, dir);
  };
  callout(LEFT_EYE_OUTER, `EYE L ${f.eyeLeft.toFixed(2)}${f.eyeLeft > BLINK ? " CLOSED" : ""}`, eye(f.eyeLeft));
  callout(RIGHT_EYE_OUTER, `EYE R ${f.eyeRight.toFixed(2)}${f.eyeRight > BLINK ? " CLOSED" : ""}`, eye(f.eyeRight));
  callout(MOUTH_CORNER, `JAW ${f.jaw.toFixed(2)}${f.jaw > MOUTH ? " OPEN" : ""}`, f.jaw > MOUTH ? `rgba(${AMBER}, 0.95)` : `rgba(${PULSE}, 0.8)`);

  const [fx, fy] = at(FOREHEAD);
  label(ctx, fx, fy - 28 * unit, `PITCH ${sign(f.pitch)}°  YAW ${sign(f.yaw)}°  ROLL ${sign(f.roll)}°`, `rgba(${PULSE}, 0.9)`, unit, 0);
  label(ctx, fx, fy - 44 * unit, `FACE MESH · 478 LANDMARKS · ${Math.round(fps)} FPS`, `rgba(${PULSE}, 0.5)`, unit, 0);
  label(ctx, fx, fy - 58 * unit, `${f.delegate} · FACE ${f.faceMs.toFixed(0)} MS`, `rgba(${PULSE}, 0.5)`, unit, 0);

  if (f.axes) {
    const [nx, ny] = at(NOSE_TIP);
    const len = 42 * unit;
    const axis = (dx: number, dy: number, color: string) => {
      ctx.strokeStyle = color;
      ctx.lineWidth = 1.6 * unit;
      ctx.beginPath();
      ctx.moveTo(nx, ny);
      ctx.lineTo(nx + dx * len, ny - dy * len); // image y grows downwards
      ctx.stroke();
    };
    const [xx, xy, yx, yy, zx, zy] = f.axes;
    axis(xx, xy, "rgba(248, 113, 113, 0.9)");
    axis(yx, yy, "rgba(52, 211, 153, 0.9)");
    axis(zx, zy, `rgba(${ORBIT}, 0.95)`);
  }
}

/** Text on a canvas that CSS mirrors: flip it back so it reads left to right. `dir` is where the callout points. */
function label(ctx: CanvasRenderingContext2D, x: number, y: number, text: string, color: string, unit: number, dir: number) {
  ctx.save();
  ctx.translate(x, y);
  ctx.scale(-1, 1);
  ctx.font = `${Math.round(11 * unit)}px "JetBrains Mono", ui-monospace, monospace`;
  ctx.textAlign = dir === 0 ? "center" : dir > 0 ? "right" : "left"; // mirrored: right on canvas reads as left on screen
  ctx.fillStyle = color;
  ctx.fillText(text, 0, 0);
  ctx.restore();
}

const sign = (n: number) => `${n >= 0 ? "+" : "−"}${Math.abs(Math.round(n))}`;
