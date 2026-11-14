"use client";

import { useEffect, useRef, useState, type ReactNode, type RefObject } from "react";
import { describeFrame, frameSignature, isSpeaking, sceneChange, speak, stopSpeaking, transcribe } from "./pulsarApi";

// Hands-free conversation. shortcut: these were tuned against a synthetic microphone only, adjust MIN_LEVEL on
// the demo laptop's real microphone and room (raise it if PULSAR reacts to noise, lower it if it misses a soft voice).
const TICK_MS = 50; // how often the microphone level is measured
const MIN_LEVEL = 0.015; // quietest level (RMS, 0 to 1) that can count as a voice
const VOICE_TICKS = 3; // 150 ms above the threshold starts a turn
const SILENCE_TICKS = 18; // 900 ms below it ends the turn and sends it
const MAX_TURN_MS = 20_000; // a turn is sent after this long even without a pause
const IDLE_RESTART_MS = 4000; // with nobody speaking, the recording is restarted this often

// shortcut: guessed threshold (0-255) that has never seen a real camera, tune it on the demo laptop's webcam and lighting.
const SCENE_CHANGE = 12;
// Rest after each description, so constant movement cannot chain model calls or cut the spoken line short.
const COOLDOWN_MS = 4000;

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
 * PULSAR's senses: VOICE reads its current line aloud, TALK opens the microphone for a hands-free conversation,
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
  /** The astronaut's order; `spoken` is true when it came through the open microphone (TALK) rather than typed. */
  onInstruction?: (text: string, spoken?: boolean) => void;
}) {
  const [voice, setVoice] = useState(false);
  const [watching, setWatching] = useState(false);
  const [listening, setListening] = useState(false); // TALK: the microphone is open
  const [hearing, setHearing] = useState(false); // the astronaut is speaking right now
  const hearingNow = useRef(false);
  const [heard, setHeard] = useState("");
  const [typed, setTyped] = useState("");
  const [error, setError] = useState("");
  const fail = (e: unknown) => setError(e instanceof Error ? e.message : String(e));

  useEffect(() => {
    if (!voice || hearingNow.current) return; // never talk over the astronaut
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
        let wait = 500;
        if (now && (!described || sceneChange(now, described) > SCENE_CHANGE)) {
          described = now;
          const seen = await describeFrame(video);
          if (!on) return;
          onSeen(seen);
          setError("");
          wait = COOLDOWN_MS;
        }
        timer = window.setTimeout(look, wait);
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

  // TALK on: an open conversation. The microphone stays open, a turn starts when the astronaut's voice rises above
  // the room noise (which also cuts PULSAR off) and is sent on its own after a short silence.
  useEffect(() => {
    if (!listening) return;
    let on = true;
    let stream: MediaStream | undefined;
    let audio: AudioContext | undefined;
    let rec: MediaRecorder | undefined;
    let timer = 0;

    const send = async (clip: Blob) => {
      try {
        const text = await transcribe(clip);
        if (!on || !text) return; // a cough or a door: nothing to act on
        setHeard(text);
        setError("");
        onInstruction?.(text, true);
      } catch (e) {
        if (on) fail(e);
      }
    };

    (async () => {
      try {
        // Ask for the clean-up explicitly: browsers differ on the defaults, and without it the speakers leak in.
        stream = await navigator.mediaDevices.getUserMedia({
          audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true, channelCount: 1 },
        });
        if (!on) return stream.getTracks().forEach((t) => t.stop());
        audio = new AudioContext();
        const analyser = audio.createAnalyser();
        analyser.fftSize = 1024;
        audio.createMediaStreamSource(stream).connect(analyser);
        const samples = new Float32Array(analyser.fftSize);

        // The recorder never stops, so the first syllable is already on tape when the voice is detected; whisper's
        // own filter drops the silence around it. `restart(true)` sends what was recorded, `restart(false)` drops it.
        let chunks: Blob[] = [];
        let started = 0;
        const restart = (keep: boolean) => {
          const done = rec;
          const clip = chunks;
          if (done) {
            done.onstop = () => keep && on && send(new Blob(clip, { type: done.mimeType }));
            done.stop();
          }
          const next: Blob[] = (chunks = []);
          rec = new MediaRecorder(stream!);
          rec.ondataavailable = (e) => next.push(e.data);
          rec.start();
          started = performance.now();
        };
        restart(false);

        let floor = MIN_LEVEL; // running estimate of the room noise
        let loud = 0;
        let quiet = 0;
        let speaking = false;
        timer = window.setInterval(() => {
          analyser.getFloatTimeDomainData(samples);
          const level = Math.sqrt(samples.reduce((sum, v) => sum + v * v, 0) / samples.length);
          // Twice as strict while PULSAR talks, so its own voice from the speakers does not count as the astronaut.
          const threshold = Math.max(MIN_LEVEL, floor * 3) * (isSpeaking() ? 2 : 1);
          if (level > threshold) {
            loud++;
            quiet = 0;
          } else {
            quiet++;
            loud = 0;
            if (!speaking) floor = floor * 0.95 + level * 0.05;
          }
          const age = performance.now() - started;
          if (!speaking && loud >= VOICE_TICKS) {
            speaking = hearingNow.current = true;
            setHearing(true);
            stopSpeaking(); // the astronaut is talking: PULSAR stops at once
          } else if (speaking && (quiet >= SILENCE_TICKS || age > MAX_TURN_MS)) {
            speaking = hearingNow.current = false;
            setHearing(false);
            restart(true);
          } else if (!speaking && quiet >= VOICE_TICKS && age > IDLE_RESTART_MS) {
            restart(false); // nobody spoke: do not let silence pile up in the recording
          }
        }, TICK_MS);
      } catch (e) {
        if (!on) return;
        fail(e); // microphone denied or missing
        setListening(false);
      }
    })();

    return () => {
      on = false;
      clearInterval(timer);
      if (rec && rec.state !== "inactive") rec.stop();
      stream?.getTracks().forEach((t) => t.stop());
      void audio?.close();
      hearingNow.current = false;
      setHearing(false);
    };
  }, [listening, onInstruction]);

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
        <Toggle on={listening} onClick={() => setListening(!listening)}>
          {!listening ? "TALK" : hearing ? "● HEARING YOU" : "● LISTENING"}
        </Toggle>
        <Toggle on={watching} disabled={!camLive} onClick={() => setWatching(!watching)}>WATCH</Toggle>
      </div>
    </div>
  );
}
