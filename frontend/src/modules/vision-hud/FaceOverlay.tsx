"use client";

import { useEffect, useRef, useState, type MutableRefObject, type RefObject } from "react";
import { createPortal } from "react-dom";
import { HudPanel, LEFT_COLUMN_ID } from "@/modules/hud/HudPanel";
import { FaceLandmarker } from "@mediapipe/tasks-vision";
import { t, useT } from "@/i18n";
import type { FaceFrame } from "./faceWorker";
import { BLINK, MOUTH_OPEN as MOUTH } from "./thresholds";
import { useAiCheck, type Tally } from "./useAiCheck";
import { useHotkey } from "@/modules/hud/useHotkey";
import { useHudAction } from "@/modules/hud/hudActions";

type Connection = { start: number; end: number };

const PULSE = "94, 242, 236"; // brand tokens (app/globals.css) as rgb, for alpha
const ORBIT = "154, 140, 255";
const AMBER = "251, 191, 36";

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
export function FaceOverlay({
  frameRef,
  videoRef,
  problem,
  menu = false,
}: {
  frameRef: MutableRefObject<FaceFrame | null>;
  videoRef: RefObject<HTMLVideoElement | null>;
  /** Why there is no mesh, when the face worker failed (e.g. the model files are missing). */
  problem?: string;
  /** The AI check panel lives in the hidden menu (right-click the version); the check itself runs either way. */
  menu?: boolean;
}) {
  const t = useT();
  const canvas = useRef<HTMLCanvasElement>(null);
  const [show, setShow] = useState(false); // the mesh drawing is opt-in (M)
  // On by default, as asked: each check is a Gemma call on the same frame, so a laptop without a GPU may see the
  // face model stutter; C turns it off.
  const [checking, setChecking] = useState(true);
  useHotkey("c", () => setChecking((c) => !c));
  // PULSAR was asked to switch the face mesh or the AI check.
  useHudAction((action) => {
    if (action.type !== "set_overlay") return;
    if (action.target === "mesh") setShow(action.on);
    else setChecking(action.on);
  });
  const fps = useRef({ last: 0, value: 0 });
  // Once switched on, the cross-check runs whenever there is a face, whether or not the mesh is drawn over it.
  const { last, tally, error } = useAiCheck(videoRef, frameRef, checking);
  const column = typeof document === "undefined" ? null : document.getElementById(LEFT_COLUMN_ID);

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
      {/* Joins the HUD's left column of panels. */}
      {column && createPortal(
      <div className={menu ? "contents" : "hidden"}>
      <HudPanel title={t("vision.overlay.title")} defaultOpen={false} up>
        <div className="flex flex-col gap-1">
          <button type="button" aria-pressed={show} onClick={() => setShow((s) => !s)} className="border border-pulse/50 px-2 py-1 text-left text-xs text-pulse">
            {t("vision.overlay.mesh", { state: show ? t("vision.overlay.yes") : t("vision.overlay.no") })}
          </button>
          <button type="button" aria-pressed={checking} onClick={() => setChecking((c) => !c)} className="border border-pulse/50 px-2 py-1 text-left text-xs text-pulse">
            {t("vision.overlay.check", { state: checking ? t("vision.overlay.yes") : t("vision.overlay.no") })}
          </button>
        </div>
        {problem && (
          <p role="alert" className="mt-2 border border-red-500 bg-red-600/30 p-2 normal-case tracking-normal text-white">
            {t("vision.overlay.noMesh", { problem, command: "make prefetch" })}
          </p>
        )}
        {last ? (
          <dl className="mt-2 space-y-1">
            <Row label={t("vision.overlay.eyes")} mp={last.claim.eyes} ai={last.ai.eyes} ok={last.agrees.eyes} tally={tally.eyes} />
            <Row label={t("vision.overlay.mouth")} mp={last.claim.mouth} ai={last.ai.mouth} ok={last.agrees.mouth} tally={tally.mouth} />
            <div className="pt-1 text-shell/70">{last.ai.person ? t("vision.overlay.faceOk") : t("vision.overlay.noFace")} · {Math.round(last.ms)} ms</div>
          </dl>
        ) : (
          <p className="mt-2 normal-case tracking-normal text-shell/70">
            {checking ? t("vision.overlay.firstCheck") : t("vision.overlay.off")}
          </p>
        )}
        {error && <p className="mt-1 text-red-300">{error}</p>}
        <p className="mt-2 text-[11px] tracking-normal text-shell/70">{t("vision.overlay.evidence")}</p>
      </HudPanel>
      </div>,
      column)}
    </>
  );
}

function Row({ label, mp, ai, ok, tally }: { label: string; mp: string; ai: string; ok: boolean | null; tally: Tally }) {
  const mark = ok === null ? "·" : ok ? "✓" : "✗";
  const tone = ok === null ? "text-shell/70" : ok ? "text-emerald-300" : "text-amber-300";
  return (
    <div className="flex justify-between">
      <dt>{label}</dt>
      <dd>
        MP {mp.toUpperCase()} · {t("vision.overlay.aiShort")} {ai.toUpperCase()} <span className={tone}>{mark}</span>{" "}
        <span className="text-shell/70">{tally.total ? `${tally.agree}/${tally.total}` : ""}</span>
      </dd>
    </div>
  );
}

const MODEL_LABEL = { alert: "vision.canvas.alert", low_vigilance: "vision.canvas.lowVigilance", drowsy: "vision.canvas.drowsy" } as const;

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
  callout(LEFT_EYE_OUTER, `${t("vision.canvas.eyeLeft")} ${f.eyeLeft.toFixed(2)}${f.eyeLeft > BLINK ? " " + t("vision.canvas.closed") : ""}`, eye(f.eyeLeft));
  callout(RIGHT_EYE_OUTER, `${t("vision.canvas.eyeRight")} ${f.eyeRight.toFixed(2)}${f.eyeRight > BLINK ? " " + t("vision.canvas.closed") : ""}`, eye(f.eyeRight));
  callout(MOUTH_CORNER, `${t("vision.canvas.jaw")} ${f.jaw.toFixed(2)}${f.jaw > MOUTH ? " " + t("vision.canvas.open") : ""}`, f.jaw > MOUTH ? `rgba(${AMBER}, 0.95)` : `rgba(${PULSE}, 0.8)`);

  const [fx, fy] = at(FOREHEAD);
  label(ctx, fx, fy - 28 * unit, t("vision.canvas.pose", { pitch: sign(f.pitch), yaw: sign(f.yaw), roll: sign(f.roll) }), `rgba(${PULSE}, 0.9)`, unit, 0);
  label(ctx, fx, fy - 44 * unit, t("vision.canvas.mesh", { fps: Math.round(fps) }), `rgba(${PULSE}, 0.5)`, unit, 0);
  label(ctx, fx, fy - 58 * unit, t("vision.canvas.face", { delegate: f.delegate, ms: f.faceMs.toFixed(0) }), `rgba(${PULSE}, 0.5)`, unit, 0);
  // The RLDD model's reading of the last minute: evidence next to the score, the rules engine does not see it.
  const drowsy = f.model?.label === "drowsy";
  const reading = f.model
    ? t("vision.canvas.score", { label: t(MODEL_LABEL[f.model.label]), score: f.model.score.toFixed(2), probs: f.model.probabilities.map((p) => Math.round(p * 100)).join("/") })
    : f.modelWaitS > 0 ? t("vision.canvas.wait", { s: Math.ceil(f.modelWaitS) }) : t("vision.canvas.unusable");
  label(ctx, fx, fy - 72 * unit, t("vision.canvas.model", { reading }), `rgba(${drowsy ? AMBER : ORBIT}, 0.95)`, unit, 0);

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
