"use client";

import { useEffect, useRef, useState, type ReactNode, type RefObject } from "react";
import { describeFrame, frameSignature, sceneChange, speak, stopSpeaking, transcribe } from "./pulsarApi";

// shortcut: guessed threshold (0-255) that has never seen a real camera, tune it on the demo laptop's webcam and lighting.
const SCENE_CHANGE = 12;

function Toggle({ on, children, ...rest }: { on: boolean; children: ReactNode } & React.ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button
      type="button"
      aria-pressed={on}
      className={`border-2 px-3 py-1 disabled:opacity-40 ${on ? "border-pulse bg-pulse/20 text-pulse" : "border-shell/40 bg-space/60 text-shell/80"}`}
      {...rest}
    >
      {children}
    </button>
  );
}

/**
 * PULSAR's senses: VOICE reads its current line aloud, TALK records the microphone and shows the transcript,
 * WATCH sends a camera frame whenever the scene changes and hands the description back through `onSeen`.
 */
export function SensesBar({
  videoRef,
  camLive,
  line,
  onSeen,
  onInstruction,
}: {
  videoRef: RefObject<HTMLVideoElement | null>;
  camLive: boolean;
  line: string;
  onSeen: (description: string | null) => void;
  /** The astronaut's order, spoken (TALK) or typed. */
  onInstruction?: (text: string) => void;
}) {
  const [voice, setVoice] = useState(false);
  const [watching, setWatching] = useState(false);
  const [talk, setTalk] = useState<"idle" | "recording" | "transcribing">("idle");
  const [heard, setHeard] = useState("");
  const [typed, setTyped] = useState("");
  const [error, setError] = useState("");
  const recorder = useRef<MediaRecorder | null>(null);
  const fail = (e: unknown) => setError(e instanceof Error ? e.message : String(e));

  useEffect(() => {
    if (!voice) return;
    speak(line).catch((e) => {
      fail(e);
      setVoice(false);
    });
    return stopSpeaking;
  }, [voice, line]);

  useEffect(() => {
    if (!watching) return;
    let on = true;
    let timer = 0;
    let described: Uint8ClampedArray | null = null;
    // The scene is compared locally twice a second; a frame goes to the model only when it has changed.
    const look = async () => {
      try {
        const video = videoRef.current!;
        const now = frameSignature(video);
        if (now && (!described || sceneChange(now, described) > SCENE_CHANGE)) {
          described = now;
          const seen = await describeFrame(video);
          if (!on) return;
          onSeen(seen);
          setError("");
        }
        timer = window.setTimeout(look, 500);
      } catch (e) {
        if (!on) return;
        fail(e);
        setWatching(false);
      }
    };
    look();
    return () => {
      on = false;
      clearTimeout(timer);
      onSeen(null);
    };
  }, [watching, videoRef, onSeen]);

  // Never leave the microphone open behind an unmounted HUD.
  useEffect(() => () => recorder.current?.stream.getTracks().forEach((t) => t.stop()), []);

  const toggleTalk = async () => {
    if (talk === "recording") return recorder.current?.stop();
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const rec = new MediaRecorder(stream);
      const chunks: Blob[] = [];
      rec.ondataavailable = (e) => chunks.push(e.data);
      rec.onstop = async () => {
        stream.getTracks().forEach((t) => t.stop());
        setTalk("transcribing");
        try {
          const text = await transcribe(new Blob(chunks, { type: rec.mimeType }));
          setHeard(text);
          if (text) onInstruction?.(text);
          setError("");
        } catch (e) {
          fail(e);
        }
        setTalk("idle");
      };
      recorder.current = rec;
      rec.start();
      setTalk("recording");
    } catch (e) {
      fail(e); // microphone denied or missing
    }
  };

  const send = (e: React.FormEvent) => {
    e.preventDefault();
    const text = typed.trim();
    if (!text) return;
    setHeard(text);
    setTyped("");
    onInstruction?.(text);
  };

  return (
    <div className="absolute inset-x-0 bottom-16 flex flex-col items-center gap-2 px-8 text-[11px] tracking-[0.2em]">
      <p role="status" className="min-h-4 max-w-xl text-center tracking-normal text-shell">
        {error ? <span className="text-orbit">{error}</span> : heard && `YOU · ${heard}`}
      </p>
      <form onSubmit={send} className="flex w-full max-w-xl gap-2">
        <input
          value={typed}
          onChange={(e) => setTyped(e.target.value)}
          maxLength={400}
          placeholder="Tell PULSAR what to do..."
          aria-label="Type an instruction for PULSAR"
          className="min-w-0 flex-1 border-2 border-shell/40 bg-space/70 px-3 py-1 tracking-normal text-shell outline-none placeholder:text-shell/40 focus:border-pulse"
        />
        <button type="submit" disabled={!typed.trim()} className="border-2 border-pulse bg-pulse/20 px-3 py-1 text-pulse disabled:opacity-40">
          SEND
        </button>
      </form>
      <div className="flex gap-2">
        <Toggle on={voice} onClick={() => setVoice(!voice)}>VOICE</Toggle>
        <Toggle on={talk === "recording"} disabled={talk === "transcribing"} onClick={toggleTalk}>
          {talk === "recording" ? "● STOP" : talk === "transcribing" ? "LISTENING…" : "TALK"}
        </Toggle>
        <Toggle on={watching} disabled={!camLive} onClick={() => setWatching(!watching)}>WATCH</Toggle>
      </div>
    </div>
  );
}
