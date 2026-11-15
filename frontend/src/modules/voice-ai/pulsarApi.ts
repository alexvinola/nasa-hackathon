/** Calls to the local PULSAR backend (backend/senses.py). Everything stays on this machine. */
import { getLang, t } from "@/i18n";

const API = process.env.NEXT_PUBLIC_PULSAR_API ?? "http://localhost:8000";

async function call(path: string, init: RequestInit): Promise<Response> {
  const response = await fetch(API + path, { method: "POST", ...init }).catch(() => {
    throw new Error(t("voice.api.unreachable", { api: API }));
  });
  if (!response.ok) {
    const detail = (await response.json().catch(() => null))?.detail;
    throw new Error(typeof detail === "string" ? detail : t("voice.api.error", { status: response.status }));
  }
  return response;
}

/** Speech to text (faster-whisper). */
export async function transcribe(audio: Blob): Promise<string> {
  return (await (await call(`/stt?lang=${getLang()}`, { body: audio })).json()).text;
}

let playing: HTMLAudioElement | null = null;
let turn = 0;
let request: AbortController | null = null;

/** True while PULSAR's voice is coming out of the speakers. */
export function isSpeaking() {
  return !!playing && !playing.paused && !playing.ended;
}

export function stopSpeaking() {
  turn++;
  request?.abort(); // do not leave Piper synthesising a line nobody will hear
  playing?.pause();
  playing = null;
}

/** Text to speech (Piper). A new call cuts the previous one off. */
export async function speak(text: string): Promise<void> {
  stopSpeaking();
  const mine = turn;
  request = new AbortController();
  let wav: Blob;
  try {
    const response = await call("/tts", {
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text: text.slice(0, 600), lang: getLang() }), // the backend's limit
      signal: request.signal,
    });
    wav = await response.blob();
  } catch (error) {
    if (mine !== turn) return; // superseded: the abort is ours, not a backend failure
    throw error;
  }
  if (mine !== turn) return;
  const url = URL.createObjectURL(wav);
  playing = new Audio(url);
  playing.onended = playing.onpause = () => URL.revokeObjectURL(url);
  await playing.play().catch((error: DOMException) => {
    if (error.name !== "AbortError") throw error; // AbortError only means stopSpeaking() got there first
  });
}

let thumb: HTMLCanvasElement | undefined;

/** A 32×18 thumbnail of the frame: cheap enough to take twice a second and compare in the browser. */
export function frameSignature(video: HTMLVideoElement): Uint8ClampedArray | null {
  if (!video.videoWidth) return null;
  thumb ??= Object.assign(document.createElement("canvas"), { width: 32, height: 18 });
  const ctx = thumb.getContext("2d", { willReadFrequently: true })!;
  ctx.drawImage(video, 0, 0, 32, 18);
  return ctx.getImageData(0, 0, 32, 18).data;
}

/** How different two signatures are: mean absolute difference of the green channel, 0 to 255. */
export function sceneChange(a: Uint8ClampedArray, b: Uint8ClampedArray): number {
  let sum = 0;
  for (let i = 1; i < a.length; i += 4) sum += Math.abs(a[i] - b[i]);
  return sum / (a.length / 4);
}

/** The current camera frame as a 640 px wide JPEG, mirrored like the HUD. */
async function grabFrame(video: HTMLVideoElement): Promise<Blob> {
  if (!video.videoWidth) throw new Error(t("voice.api.noPicture"));
  const canvas = document.createElement("canvas");
  canvas.width = 640; // enough for a scene description and keeps the model fast
  canvas.height = Math.round((640 * video.videoHeight) / video.videoWidth);
  const ctx = canvas.getContext("2d")!;
  ctx.setTransform(-1, 0, 0, 1, canvas.width, 0); // mirrored like the HUD, so "left" and "right" match what the user sees
  ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
  const frame = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, "image/jpeg", 0.7));
  if (!frame) throw new Error(t("voice.api.noFrame"));
  return frame;
}

/** Sends the current camera frame to the local vision model and returns what it sees. */
export async function describeFrame(video: HTMLVideoElement): Promise<string> {
  return (await (await call("/vision/describe", { body: await grabFrame(video) })).json()).description;
}

/** The current frame as base64, for `direct`; undefined when the camera has no picture. */
export async function frameBase64(video: HTMLVideoElement | null): Promise<string | undefined> {
  if (!video?.videoWidth) return undefined;
  const bytes = new Uint8Array(await (await grabFrame(video)).arrayBuffer());
  let binary = "";
  for (const byte of bytes) binary += String.fromCharCode(byte);
  return btoa(binary);
}

let waiting = 0;

/**
 * True while the astronaut is waiting for PULSAR to answer. There is one model and it serves one request at a
 * time, so background jobs (camera descriptions, AI checks) skip their turn rather than queue ahead of the answer.
 */
export function userWaiting() {
  return waiting > 0;
}

export type Spot ="home" | "top_right" | "mid_left" | "mid_right" | "bottom_left" | "bottom_center" | "bottom_right";
export type Direction = { say: string; spot: Spot | ""; reaction: "calm" | "alert"; speak: boolean };

/**
 * Asks Gemma (via the backend) where PULSAR goes, how it reacts and what it says. `instruction` is the astronaut's
 * latest order (voice or typed), `userSpoke` is true when it is new, and `said` is what PULSAR already said so it
 * does not repeat itself. `speak: false` in the answer means there is nothing worth saying. `image` (base64 JPEG)
 * lets the model look at the frame itself; it roughly doubles the wait, so send it only when there is no `seen`.
 */
export async function direct(scene: {
  image?: string;
  seen?: string;
  instruction?: string;
  userSpoke: boolean;
  /** The instruction came through the open microphone, so the backend may decide it was not meant for PULSAR. */
  viaVoice?: boolean;
  /** PULSAR spoke moments ago: what the microphone hears now is a reply to it. */
  engaged?: boolean;
  /** Earlier turns, oldest first ("Astronaut: ..." / "PULSAR: ..."); the backend compacts them. */
  history?: string[];
  /** The current readings (the full contract): the backend's rules engine turns them into PULSAR's health check. */
  telemetry?: unknown;
  said: string[];
  spot: Spot;
}): Promise<Direction> {
  const { userSpoke, viaVoice, ...rest } = scene;
  if (userSpoke) waiting++;
  try {
    return await (
      await call("/pulsar/act", {
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...rest, lang: getLang(), user_spoke: userSpoke, via_voice: viaVoice, history: scene.history?.map((t) => t.slice(0, 300)) }),
      })
    ).json();
  } finally {
    if (userSpoke) waiting--;
  }
}
