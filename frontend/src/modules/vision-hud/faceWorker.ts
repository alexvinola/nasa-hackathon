/**
 * MediaPipe in a Web Worker: face landmarks in, the `biometrics` block of the contract out.
 * It runs off the main thread so the HUD keeps its frame rate, and nothing leaves the machine except the
 * numbers the HUD posts to the local backend.
 *
 * Fatigue is read from the face only. The pose model is not loaded: at a laptop the arms are mostly out of the
 * frame and MediaPipe guesses them, so `armAsymmetry` raised false alarms. The contract still requires the field,
 * so it is sent as 0 (not measured by the camera).
 *
 * The score is a fixed-weight proposal (goals/SCOPE-fatigue.md, Tier 0): PERCLOS dominates, yawns and head
 * instability add to it. G2 replaces the weights with a trained model; until then this is a threshold, not a verdict.
 */

import { FaceLandmarker, FilesetResolver } from "@mediapipe/tasks-vision";
import { BLINK } from "./thresholds";
import { mouthOpenRatio, YawnDetector } from "./yawn";

type Frame = { type: "frame"; bitmap: ImageBitmap; at: number };
type Stop = { type: "stop" };
type Warm = { type: "warm" }; // load the models now, before the first frame arrives
type In = Frame | Stop | Warm;

export type Biometrics = {
  heartRateBpm: number | null;
  heartRateConfidence: number;
  fatigueScore: number;
  perclos: number;
  yawnsPerMin: number;
  postureStability: number;
  armAsymmetry: number;
  lastPvtMeanMs: number | null;
  lastPvtLapses: number | null;
};

/** What the overlay draws for one frame: every landmark MediaPipe found plus the values the metrics use. */
export type FaceFrame = {
  at: number;
  width: number;
  height: number;
  face: Float32Array | null; // 478 landmarks × (x, y, z), normalised to the frame
  eyeLeft: number; // eyeBlinkLeft blendshape, 0 open to 1 closed (above BLINK counts as closed)
  eyeRight: number;
  jaw: number; // jawOpen blendshape, drawn by the overlay; yawns are counted from the lip ratio in ./yawn
  pitch: number; // head pose in degrees, from the facial transformation matrix
  yaw: number;
  roll: number;
  axes: number[] | null; // the head's x, y, z axes projected on the image: [xx, xy, yx, yy, zx, zy]
  delegate: "GPU" | "CPU";
  faceMs: number; // time spent in the face model for this frame
};

const scope = self as unknown as {
  onmessage: ((event: MessageEvent<In>) => void) | null;
  postMessage: (message: unknown, transfer?: Transferable[]) => void;
};

const WINDOW_MS = 60_000; // PERCLOS is the share of the last minute with the eyes closed
const NOD = 0.03; // nose drop, as a fraction of frame height, that counts as a head nod

let face: FaceLandmarker | undefined;
let busy = false;
let ready: Promise<void> | undefined;
let delegate: "GPU" | "CPU" = "GPU";

const eyes: { at: number; closed: boolean }[] = [];
const yawns: number[] = []; // when each yawn was counted, in ms
const yawnDetector = new YawnDetector(); // calibrated on YawDD: lip ratio ≥ 0.26 held for ≥ 1 s, counted once
const nods: number[] = [];
const noseY: number[] = [];

/** Loads the model once. Tries the GPU (WebGL in the worker) and falls back to the CPU if the browser refuses. */
function load(): Promise<void> {
  ready ??= (async () => {
    const fileset = await FilesetResolver.forVisionTasks("/mediapipe/wasm");
    const create = (use: "GPU" | "CPU") =>
      FaceLandmarker.createFromOptions(fileset, {
        baseOptions: { modelAssetPath: "/mediapipe/face_landmarker.task", delegate: use },
        runningMode: "VIDEO",
        numFaces: 1,
        outputFaceBlendshapes: true,
        outputFacialTransformationMatrixes: true,
      });
    try {
      face = await create("GPU");
    } catch {
      delegate = "CPU";
      face = await create("CPU");
    }
  })();
  return ready;
}

const clamp01 = (n: number) => Math.min(1, Math.max(0, n));
const mean = (xs: number[]) => (xs.length ? xs.reduce((a, b) => a + b, 0) / xs.length : 0);

function prune(now: number) {
  while (eyes.length && now - eyes[0].at > WINDOW_MS) eyes.shift();
  while (yawns.length && now - yawns[0] > WINDOW_MS) yawns.shift();
  while (nods.length && now - nods[0] > WINDOW_MS) nods.shift();
  while (noseY.length > 90) noseY.shift();
}

function score(now: number): Biometrics {
  prune(now);
  const perclos = eyes.length ? eyes.filter((e) => e.closed).length / eyes.length : 0;
  const yawnsPerMin = yawns.length; // the window is one minute
  const spread = Math.sqrt(mean(noseY.map((y) => (y - mean(noseY)) ** 2)));
  const postureStability = clamp01(1 - spread * 12);
  // 0.8 PERCLOS + 0.1 yawns (4 a minute saturates) + 0.1 head instability. Team assumption until G2 trains the
  // weights: PERCLOS is the eye measure validated against PVT lapses (dinges-1998-ocular), and eyes held closed must
  // be able to cross 0.7 on their own (goals/G1-camera-fatigue.md); with 0.6 the ceiling was 0.6.
  const fatigueScore = clamp01(0.8 * perclos + 0.1 * Math.min(1, yawnsPerMin / 4) + 0.1 * (1 - postureStability));
  return {
    heartRateBpm: null, // rPPG is a stretch goal (SCOPE-fatigue.md)
    heartRateConfidence: 0,
    fatigueScore: Number(fatigueScore.toFixed(3)),
    perclos: Number(perclos.toFixed(3)),
    yawnsPerMin: Number(yawnsPerMin.toFixed(1)),
    postureStability: Number(postureStability.toFixed(3)),
    armAsymmetry: 0, // not measured: the camera reads the face only
    lastPvtMeanMs: null,
    lastPvtLapses: null,
  };
}

function readFace(result: ReturnType<FaceLandmarker["detectForVideo"]>, now: number, width: number, height: number) {
  const landmarks = result.faceLandmarks?.[0];
  // Every frame goes to the detector, with a NaN ratio when there is no face: a lost face must not end a yawn early.
  if (yawnDetector.push(now / 1000, mouthOpenRatio(landmarks, width, height))) yawns.push(now);
  const shapes = result.faceBlendshapes?.[0]?.categories;
  if (!shapes) return;
  const at = (name: string) => shapes.find((c) => c.categoryName === name)?.score ?? 0;
  eyes.push({ at: now, closed: (at("eyeBlinkLeft") + at("eyeBlinkRight")) / 2 > BLINK });
  if (landmarks) {
    const nose = landmarks[1] ?? landmarks[0];
    const before = noseY[noseY.length - 1];
    noseY.push(nose.y);
    if (before !== undefined && nose.y - before > NOD) nods.push(now);
  }
}

const DEG = 180 / Math.PI;

function frameOf(
  faceResult: ReturnType<FaceLandmarker["detectForVideo"]>,
  bitmap: ImageBitmap,
  at: number,
  faceMs: number,
): FaceFrame {
  const landmarks = faceResult.faceLandmarks?.[0];
  const shapes = faceResult.faceBlendshapes?.[0]?.categories ?? [];
  const shape = (name: string) => shapes.find((c) => c.categoryName === name)?.score ?? 0;
  // Column-major 4×4 rotation + translation of the canonical face (MediaPipe face geometry).
  const m = faceResult.facialTransformationMatrixes?.[0]?.data;
  return {
    at,
    width: bitmap.width,
    height: bitmap.height,
    face: landmarks ? Float32Array.from(landmarks.flatMap((l) => [l.x, l.y, l.z])) : null,
    eyeLeft: shape("eyeBlinkLeft"),
    eyeRight: shape("eyeBlinkRight"),
    jaw: shape("jawOpen"),
    pitch: m ? Math.atan2(m[6], m[10]) * DEG : 0,
    yaw: m ? Math.atan2(-m[2], Math.hypot(m[6], m[10])) * DEG : 0,
    roll: m ? Math.atan2(m[1], m[0]) * DEG : 0,
    axes: m ? [m[0], m[1], m[4], m[5], m[8], m[9]] : null,
    delegate,
    faceMs,
  };
}

async function handle(frame: Frame) {
  if (busy) {
    frame.bitmap.close(); // drop the frame instead of queueing: a stale frame is worth nothing
    return;
  }
  busy = true;
  try {
    await load();
    const now = frame.at;
    const t0 = performance.now();
    const faceResult = face!.detectForVideo(frame.bitmap, now);
    const faceMs = performance.now() - t0;
    readFace(faceResult, now, frame.bitmap.width, frame.bitmap.height);
    scope.postMessage({ type: "biometrics", biometrics: score(now), at: now });
    const drawn = frameOf(faceResult, frame.bitmap, now, faceMs);
    scope.postMessage({ type: "face", frame: drawn }, drawn.face ? [drawn.face.buffer as ArrayBuffer] : []); // transferred, not copied
  } catch (error) {
    scope.postMessage({ type: "error", message: error instanceof Error ? error.message : String(error) });
  } finally {
    frame.bitmap.close();
    busy = false;
  }
}

scope.onmessage = (event) => {
  const message = event.data;
  if (message.type === "frame") void handle(message);
  if (message.type === "warm") {
    load().catch((error) => scope.postMessage({ type: "error", message: error instanceof Error ? error.message : String(error) }));
  }
  if (message.type === "stop") {
    eyes.length = 0;
    yawns.length = 0;
    yawnDetector.reset();
    nods.length = 0;
    noseY.length = 0;
  }
};
