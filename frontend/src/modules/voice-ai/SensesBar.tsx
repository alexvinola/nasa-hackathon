"use client";

import { useEffect, useRef, useState } from "react";
import { useT } from "@/i18n";
import { useHotkey } from "@/modules/hud/useHotkey";
import { isSpeaking, speak, stopSpeaking, transcribe } from "./pulsarApi";

// Solid, dark-on-light or light-on-dark: the HUD sits over a camera picture that can be a bright white room, where
// translucent panels and pale text disappear.
const BUTTON = "border-2 px-4 py-2 font-bold disabled:border-shell/50 disabled:bg-space/90 disabled:text-shell/60";
const OFF = "border-shell bg-space/90 text-shell";
const ON = "border-pulse bg-pulse text-space";

/**
 * PULSAR's controls. Nothing here runs on its own: SEND answers what was typed, HOLD TO TALK records while the
 * mic button (or the space bar) is held and sends when it is released. PULSAR reads each new line of its own aloud
 * (the S key stops it or repeats it). The input, the mic and the send arrow sit on one row, like a chat.
 */
export function SensesBar({
  line,
  onInstruction,
}: {
  line: string;
  /** The astronaut's order, typed or spoken. */
  onInstruction?: (text: string) => void;
}) {
  const t = useT();
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
          setError(text ? "" : t("voice.senses.heardNothing"));
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
  // PULSAR always speaks what it says. A browser that has not yet had a click may refuse to play: that is not an error.
  useEffect(() => {
    if (line) speak(line).catch((e) => e?.name !== "NotAllowedError" && fail(e));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [line]);
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
      {/* Never under the side columns: 16rem on the left and 20rem on the right, plus margins, stay free. */}
      <div data-hud-panel className="pointer-events-auto flex w-full min-w-72 max-w-[min(42rem,calc(100vw-44rem))] flex-col items-center gap-2">
        {/* What PULSAR understood, on a solid plate so it can be checked against what was said or typed. */}
        <p role="status" className="min-h-8 text-center text-lg tracking-normal">
          {error ? (
            <span className="inline-block border-2 border-red-500 bg-space/95 px-3 py-1 text-red-200">{error}</span>
          ) : (
            heard && (
              <span className="inline-block border-2 border-pulse bg-space/95 px-3 py-1 text-white">
                <span className="mr-2 text-sm font-bold tracking-[0.15em] text-pulse">{t("voice.senses.youSaid")}</span>
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
            placeholder={t("voice.senses.placeholder")}
            aria-label={t("voice.senses.inputLabel")}
            className="min-w-0 flex-1 border-2 border-shell bg-space/95 px-3 py-2 text-lg tracking-normal text-white outline-none placeholder:text-shell/70 focus:border-pulse"
          />
          <button
            type="button"
            aria-pressed={talk === "recording"}
            aria-label={talk === "recording" ? t("voice.senses.release") : talk === "transcribing" ? t("voice.senses.transcribing") : t("voice.senses.hold")}
            title={talk === "recording" ? t("voice.senses.release") : t("voice.senses.hold")}
            disabled={talk === "transcribing"}
            onPointerDown={press}
            onPointerUp={release}
            onPointerLeave={release}
            onPointerCancel={release}
            className={`${BUTTON} grid place-items-center px-3 touch-none select-none ${talk === "recording" ? "animate-pulse border-red-500 bg-red-600 text-white" : OFF}`}
          >
            <svg aria-hidden viewBox="0 0 24 24" className="h-6 w-6" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="9" y="2" width="6" height="12" rx="3" /><path d="M5 11a7 7 0 0 0 14 0M12 18v4" /></svg>
          </button>
          <button type="submit" aria-label={t("voice.senses.send")} title={t("voice.senses.send")} disabled={!typed.trim()} className={`${BUTTON} grid place-items-center px-3 ${ON}`}>
            <svg aria-hidden viewBox="0 0 24 24" className="h-6 w-6" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><path d="M12 19V5M5 12l7-7 7 7" /></svg>
          </button>
        </form>
      </div>
    </div>
  );
}
