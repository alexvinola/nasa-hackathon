/** Calls to the local PULSAR backend (backend/senses.py). Everything stays on this machine. */
const API = process.env.NEXT_PUBLIC_PULSAR_API ?? "http://localhost:8000";

async function call(path: string, init: RequestInit): Promise<Response> {
  const response = await fetch(API + path, { method: "POST", ...init }).catch(() => {
    throw new Error(`PULSAR backend is not answering at ${API}`);
  });
  if (!response.ok) {
    const detail = (await response.json().catch(() => null))?.detail;
    throw new Error(typeof detail === "string" ? detail : `Backend error ${response.status}`);
  }
  return response;
}

/** Speech to text (faster-whisper). */
export async function transcribe(audio: Blob): Promise<string> {
  return (await (await call("/stt", { body: audio })).json()).text;
}

let playing: HTMLAudioElement | null = null;
let turn = 0;

export function stopSpeaking() {
  turn++;
  playing?.pause();
  playing = null;
}

/** Text to speech (Piper). A new call cuts the previous one off. */
export async function speak(text: string): Promise<void> {
  stopSpeaking();
  const mine = turn;
  const response = await call("/tts", {
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text: text.slice(0, 600) }), // the backend's limit
  });
  const url = URL.createObjectURL(await response.blob());
  if (mine !== turn) return URL.revokeObjectURL(url); // superseded while Piper was synthesising
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

/** Sends the current camera frame to the local vision model and returns what it sees. */
export async function describeFrame(video: HTMLVideoElement): Promise<string> {
  if (!video.videoWidth) throw new Error("The camera has no picture yet");
  const canvas = document.createElement("canvas");
  canvas.width = 640; // enough for a scene description and keeps the model fast
  canvas.height = Math.round((640 * video.videoHeight) / video.videoWidth);
  canvas.getContext("2d")!.drawImage(video, 0, 0, canvas.width, canvas.height);
  const frame = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, "image/jpeg", 0.7));
  if (!frame) throw new Error("Could not read the camera frame");
  return (await (await call("/vision/describe", { body: frame })).json()).description;
}
