/**
 * MediaPipe in a Web Worker: face and pose landmarks in, the `biometrics` block of the contract out.
 * It runs off the main thread so the HUD keeps its frame rate, and nothing leaves the machine except the
 * numbers the HUD posts to the local backend.
 *
 * The score is a fixed-weight proposal (goals/SCOPE-fatigue.md, Tier 0): PERCLOS dominates, yawns and head
 * instability add to it. G2 replaces the weights with a trained model; until then this is a threshold, not a verdict.
 */

import { FaceLandmarker, FilesetResolver, PoseLandmarker } from "@mediapipe/tasks-vision";

type Frame = { type: "frame"; bitmap: ImageBitmap; at: number };
type Stop = { type: "stop" };
type In = Frame | Stop;

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

const scope = self as unknown as {
  onmessage: ((event: MessageEvent<In>) => void) | null;
  postMessage: (message: unknown, transfer?: Transferable[]) => void;
};

const WINDOW_MS = 60_000; // PERCLOS is the share of the last minute with the eyes closed
const BLINK = 0.5; // blendshape score above which an eye counts as closed
const YAWN = 0.5;
const NOD = 0.03; // nose drop, as a fraction of frame height, that counts as a head nod

let face: FaceLandmarker | undefined;
let pose: PoseLandmarker | undefined;
let busy = false;

const eyes: { at: number; closed: boolean }[] = [];
const yawns: number[] = [];
const nods: number[] = [];
const noseY: number[] = [];

async function load() {
  const fileset = await FilesetResolver.forVisionTasks("/mediapipe/wasm");
  face ??= await FaceLandmarker.createFromOptions(fileset, {
    baseOptions: { modelAssetPath: "/mediapipe/face_landmarker.task", delegate: "CPU" },
    runningMode: "VIDEO",
    numFaces: 1,
    outputFaceBlendshapes: true,
    outputFacialTransformationMatrixes: true,
  });
  pose ??= await PoseLandmarker.createFromOptions(fileset, {
    baseOptions: { modelAssetPath: "/mediapipe/pose_landmarker_lite.task", delegate: "CPU" },
    runningMode: "VIDEO",
    numPoses: 1,
  });
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
  const open = at("jawOpen");
  const wasOpen = yawns.length > 0 && now - yawns[yawns.length - 1] < 1500;
  if (open > YAWN && !wasOpen) yawns.push(now);
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

async function handle(frame: Frame) {
  if (busy) {
    frame.bitmap.close(); // drop the frame instead of queueing: a stale frame is worth nothing
    return;
  }
  busy = true;
  try {
    await load();
    const now = frame.at;
    readFace(face!.detectForVideo(frame.bitmap, now), now);
    readPose(pose!.detectForVideo(frame.bitmap, now));
    scope.postMessage({ type: "biometrics", biometrics: score(now), at: now });
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
  if (message.type === "stop") {
    eyes.length = 0;
    yawns.length = 0;
    nods.length = 0;
    noseY.length = 0;
  }
};
