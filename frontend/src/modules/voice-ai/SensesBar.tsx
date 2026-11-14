"use client";

import { useEffect, useRef, useState } from "react";
import { useHotkey } from "@/modules/hud/useHotkey";
import { isSpeaking, speak, stopSpeaking, transcribe } from "./pulsarApi";

// Solid, dark-on-light or light-on-dark: the HUD sits over a camera picture that can be a bright white room, where
// translucent panels and pale text disappear.
const BUTTON = "border-2 px-4 py-2 font-bold disabled:border-shell/50 disabled:bg-space/90 disabled:text-shell/60";
const OFF = "border-shell bg-space/90 text-shell";
const ON = "border-pulse bg-pulse text-space";

/**
 * PULSAR's controls. Nothing here runs on its own: SEND answers what was typed, HOLD TO TALK records while the
 * button (or the space bar) is held and sends when it is released, and SPEAK reads PULSAR's current line aloud.
 * Each label names the key that does the same.
 */
export function SensesBar({
  line,
  onInstruction,
}: {
  line: string;
  /** The astronaut's order, typed or spoken. */
  onInstruction?: (text: string) => void;
}) {
  const [talk, setTalk] = useState<"idle" | "recording" | "transcribing">("idle");
  const [heard, setHeard] = useState("");
  const [typed, setTyped] = useState("");
  const [error, setError] = useState("");
  const fail = (e: unknown) => setError(e instanceof Error ? e.message : String(e));

  // Push to talk. The microphone is opened on the first press and then kept, because opening it takes long enough
  // to swallow the first word; it only ever records while the button is held.
  const mic = useRef<MediaStream | null>(null);
  const recorder = useRef<MediaRecorder | null>(null);
  const held = useRef(false);
  useEffect(() => () => mic.current?.getTracks().forEach((t) => t.stop()), []);

  const press = async () => {
    if (held.current || talk === "transcribing") return;
    held.current = true;
    stopSpeaking(); // the astronaut is talking: PULSAR stops at once
    try {
      // Ask for the clean-up explicitly: browsers differ on the defaults, and without it the speakers leak in.
      mic.current ??= await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true, channelCount: 1 },
      });
      if (!held.current) return; // released before the microphone was ready
      const rec = new MediaRecorder(mic.current);
      const chunks: Blob[] = [];
      rec.ondataavailable = (e) => chunks.push(e.data);
      rec.onstop = async () => {
        setTalk("transcribing");
        try {
          const text = await transcribe(new Blob(chunks, { type: rec.mimeType }));
          setHeard(text);
          setError(text ? "" : "I could not hear anything. Hold the button while you speak.");
          if (text) onInstruction?.(text);
        } catch (e) {
          fail(e);
        }
        setTalk("idle");
      };
      recorder.current = rec;
      rec.start();
      setTalk("recording");
    } catch (e) {
      held.current = false;
      fail(e); // microphone denied or missing
    }
  };
  const release = () => {
    held.current = false;
    if (recorder.current?.state === "recording") recorder.current.stop();
  };
  const speakLine = () => {
    if (isSpeaking()) stopSpeaking();
    else if (line) speak(line).catch(fail);
  };
  useHotkey(" ", press, release);
  useHotkey("s", speakLine);

  const send = (e: React.FormEvent) => {
    e.preventDefault();
    const text = typed.trim();
    if (!text) return;
    setHeard(text);
    setTyped("");
    onInstruction?.(text);
  };

  return (
    <div className="pointer-events-none absolute inset-x-0 bottom-16 flex justify-center px-8 text-sm tracking-[0.15em]">
      <div data-hud-panel className="pointer-events-auto flex w-full max-w-2xl flex-col items-center gap-2">
        {/* What PULSAR understood, on a solid plate so it can be checked against what was said or typed. */}
        <p role="status" className="min-h-8 text-center text-lg tracking-normal">
          {error ? (
            <span className="inline-block border-2 border-red-500 bg-space/95 px-3 py-1 text-red-200">{error}</span>
          ) : (
            heard && (
              <span className="inline-block border-2 border-pulse bg-space/95 px-3 py-1 text-white">
                <span className="mr-2 text-sm font-bold tracking-[0.15em] text-pulse">YOU SAID</span>
                {heard}
              </span>
            )
          )}
        </p>
        <form onSubmit={send} className="flex w-full gap-2">
          <input
            value={typed}
            onChange={(e) => setTyped(e.target.value)}
            maxLength={400}
            placeholder="Tell PULSAR what to do..."
            aria-label="Type an instruction for PULSAR"
            className="min-w-0 flex-1 border-2 border-shell bg-space/95 px-3 py-2 text-lg tracking-normal text-white outline-none placeholder:text-shell/70 focus:border-pulse"
          />
          <button type="submit" disabled={!typed.trim()} className={`${BUTTON} ${ON}`}>
            SEND (ENTER)
          </button>
        </form>
        <div className="flex gap-2">
          <button type="button" disabled={!line} onClick={speakLine} className={`${BUTTON} ${OFF}`}>
            ▶ SPEAK (S)
          </button>
          <button
            type="button"
            aria-pressed={talk === "recording"}
            disabled={talk === "transcribing"}
            onPointerDown={press}
            onPointerUp={release}
            onPointerLeave={release}
            onPointerCancel={release}
            className={`${BUTTON} touch-none select-none ${talk === "recording" ? "border-red-500 bg-red-600 text-white" : OFF}`}
          >
            {talk === "recording" ? "● RELEASE TO SEND" : talk === "transcribing" ? "TRANSCRIBING…" : "HOLD TO TALK (SPACE)"}
          </button>
        </div>
      </div>
    </div>
  );
}
