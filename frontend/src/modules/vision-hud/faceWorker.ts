/**
 * MediaPipe in a Web Worker: face and pose landmarks in, the `biometrics` block of the contract out.
 * It runs off the main thread so the HUD keeps its frame rate, and nothing leaves the machine except the
 * numbers the HUD posts to the local backend.
 *
 * The score is a fixed-weight proposal (goals/SCOPE-fatigue.md, Tier 0): PERCLOS dominates, yawns and head
 * instability add to it. G2 replaces the weights with a trained model; until then this is a threshold, not a verdict.
 */

import { FaceLandmarker, FilesetResolver, PoseLandmarker } from "@mediapipe/tasks-vision";
import { BLINK, MOUTH_OPEN, YAWN_MS } from "./thresholds";

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
  pose: Float32Array | null; // 33 landmarks × (x, y, visibility)
  eyeLeft: number; // eyeBlinkLeft blendshape, 0 open to 1 closed (above BLINK counts as closed)
  eyeRight: number;
  jaw: number; // jawOpen blendshape (above YAWN starts a yawn)
  pitch: number; // head pose in degrees, from the facial transformation matrix
  yaw: number;
  roll: number;
  axes: number[] | null; // the head's x, y, z axes projected on the image: [xx, xy, yx, yy, zx, zy]
  delegate: "GPU" | "CPU";
  faceMs: number; // time spent in the face model for this frame
  poseMs: number; // time in the pose model, 0 on the frames it skips
};

const scope = self as unknown as {
  onmessage: ((event: MessageEvent<In>) => void) | null;
  postMessage: (message: unknown, transfer?: Transferable[]) => void;
};

const WINDOW_MS = 60_000; // PERCLOS is the share of the last minute with the eyes closed
const NOD = 0.03; // nose drop, as a fraction of frame height, that counts as a head nod
const POSE_EVERY = 3; // arm asymmetry changes slowly: the pose model runs on one frame in three

let face: FaceLandmarker | undefined;
let pose: PoseLandmarker | undefined;
let busy = false;
let ready: Promise<void> | undefined;
let delegate: "GPU" | "CPU" = "GPU";
let frames = 0;
let lastPose: ReturnType<PoseLandmarker["detectForVideo"]> | undefined;

const eyes: { at: number; closed: boolean }[] = [];
const yawns: number[] = [];
let mouthOpenSince: number | undefined;
let yawnCounted = false;
const nods: number[] = [];
const noseY: number[] = [];

/** Loads both models once. Tries the GPU (WebGL in the worker) and falls back to the CPU if the browser refuses. */
function load(): Promise<void> {
  ready ??= (async () => {
    const fileset = await FilesetResolver.forVisionTasks("/mediapipe/wasm");
    const create = (use: "GPU" | "CPU") =>
      Promise.all([
        FaceLandmarker.createFromOptions(fileset, {
          baseOptions: { modelAssetPath: "/mediapipe/face_landmarker.task", delegate: use },
          runningMode: "VIDEO",
          numFaces: 1,
          outputFaceBlendshapes: true,
          outputFacialTransformationMatrixes: true,
        }),
        PoseLandmarker.createFromOptions(fileset, {
          baseOptions: { modelAssetPath: "/mediapipe/pose_landmarker_lite.task", delegate: use },
          runningMode: "VIDEO",
          numPoses: 1,
        }),
      ]);
    try {
      [face, pose] = await create("GPU");
    } catch {
      delegate = "CPU";
      [face, pose] = await create("CPU");
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

let armAsymmetry = 0;

function score(now: number): Biometrics {
  prune(now);
  const perclos = eyes.length ? eyes.filter((e) => e.closed).length / eyes.length : 0;
  const yawnsPerMin = yawns.length; // the window is one minute
  const spread = Math.sqrt(mean(noseY.map((y) => (y - mean(noseY)) ** 2)));
  const postureStability = clamp01(1 - spread * 12);
  // 0.6 PERCLOS + 0.25 yawns (4 a minute saturates) + 0.15 head instability
  const fatigueScore = clamp01(0.6 * perclos + 0.25 * Math.min(1, yawnsPerMin / 4) + 0.15 * (1 - postureStability));
  return {
    heartRateBpm: null, // rPPG is a stretch goal (SCOPE-fatigue.md)
    heartRateConfidence: 0,
    fatigueScore: Number(fatigueScore.toFixed(3)),
    perclos: Number(perclos.toFixed(3)),
    yawnsPerMin: Number(yawnsPerMin.toFixed(1)),
    postureStability: Number(postureStability.toFixed(3)),
    armAsymmetry,
    lastPvtMeanMs: null,
    lastPvtLapses: null,
  };
}

function readFace(result: ReturnType<FaceLandmarker["detectForVideo"]>, now: number) {
  const shapes = result.faceBlendshapes?.[0]?.categories;
  if (!shapes) return;
  const at = (name: string) => shapes.find((c) => c.categoryName === name)?.score ?? 0;
  eyes.push({ at: now, closed: (at("eyeBlinkLeft") + at("eyeBlinkRight")) / 2 > BLINK });
  // A yawn is one long opening of the mouth: counted once, when it has lasted YAWN_MS. A word spoken with the
  // mouth wide open is too short to count, and a long yawn is not counted again every second and a half.
  if (at("jawOpen") > MOUTH_OPEN) {
    mouthOpenSince ??= now;
    if (!yawnCounted && now - mouthOpenSince >= YAWN_MS) {
      yawns.push(now);
      yawnCounted = true;
    }
  } else {
    mouthOpenSince = undefined;
    yawnCounted = false;
  }
  const landmarks = result.faceLandmarks?.[0];
  if (landmarks) {
    const nose = landmarks[1] ?? landmarks[0];
    const before = noseY[noseY.length - 1];
    noseY.push(nose.y);
    if (before !== undefined && nose.y - before > NOD) nods.push(now);
  }
}

function readPose(result: ReturnType<PoseLandmarker["detectForVideo"]>) {
  const points = result.landmarks?.[0];
  if (!points) return;
  const [leftWrist, rightWrist, leftShoulder, rightShoulder] = [15, 16, 11, 12].map((i) => points[i]);
  if (!leftWrist || !rightWrist || !leftShoulder || !rightShoulder) return;
  const width = Math.abs(leftShoulder.x - rightShoulder.x) || 0.1;
  armAsymmetry = clamp01(Math.abs(leftWrist.y - rightWrist.y) / width / 2);
}

const DEG = 180 / Math.PI;

function frameOf(
  faceResult: ReturnType<FaceLandmarker["detectForVideo"]>,
  poseResult: ReturnType<PoseLandmarker["detectForVideo"]>,
  bitmap: ImageBitmap,
  at: number,
  faceMs: number,
  poseMs: number,
): FaceFrame {
  const landmarks = faceResult.faceLandmarks?.[0];
  const points = poseResult.landmarks?.[0];
  const shapes = faceResult.faceBlendshapes?.[0]?.categories ?? [];
  const shape = (name: string) => shapes.find((c) => c.categoryName === name)?.score ?? 0;
  // Column-major 4×4 rotation + translation of the canonical face (MediaPipe face geometry).
  const m = faceResult.facialTransformationMatrixes?.[0]?.data;
  return {
    at,
    width: bitmap.width,
    height: bitmap.height,
    face: landmarks ? Float32Array.from(landmarks.flatMap((l) => [l.x, l.y, l.z])) : null,
    pose: points ? Float32Array.from(points.flatMap((l) => [l.x, l.y, l.visibility ?? 0])) : null,
    eyeLeft: shape("eyeBlinkLeft"),
    eyeRight: shape("eyeBlinkRight"),
    jaw: shape("jawOpen"),
    pitch: m ? Math.atan2(m[6], m[10]) * DEG : 0,
    yaw: m ? Math.atan2(-m[2], Math.hypot(m[6], m[10])) * DEG : 0,
    roll: m ? Math.atan2(m[1], m[0]) * DEG : 0,
    axes: m ? [m[0], m[1], m[4], m[5], m[8], m[9]] : null,
    delegate,
    faceMs,
    poseMs,
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
    const t1 = performance.now();
    const runPose = frames++ % POSE_EVERY === 0 || !lastPose;
    if (runPose) {
      lastPose = pose!.detectForVideo(frame.bitmap, now);
      readPose(lastPose);
    }
    const poseMs = runPose ? performance.now() - t1 : 0;
    readFace(faceResult, now);
    scope.postMessage({ type: "biometrics", biometrics: score(now), at: now });
    const drawn = frameOf(faceResult, lastPose!, frame.bitmap, now, t1 - t0, poseMs);
    const buffers = [drawn.face, drawn.pose].filter((b): b is Float32Array => b !== null).map((b) => b.buffer as ArrayBuffer);
    scope.postMessage({ type: "face", frame: drawn }, buffers); // transferred, not copied
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
    nods.length = 0;
    noseY.length = 0;
    mouthOpenSince = undefined;
    yawnCounted = false;
  }
};
