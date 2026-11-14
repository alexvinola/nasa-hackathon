"use client";

import { useEffect } from "react";
import { isSpeaking } from "@/modules/voice-ai/pulsarApi";

export type AlarmLevel = "rest" | "danger" | null;

/**
 * The alarm you hear, made with the Web Audio API so it needs no sound file. "Time to rest" is one soft falling
 * chime. "Danger" is the klaxon of docs/brand/pulsar-intro.html (a square wave rising from 520 to 900 Hz every
 * 0.9 s, behind a 1900 Hz low-pass), repeated until the alarm clears or `silenced` is set.
 * Browsers keep a page silent until the user has clicked or typed on it once; until then nothing plays.
 */
export function useAlarmSound(level: AlarmLevel, silenced = false) {
  useEffect(() => {
    if (!level || silenced) return;
    const audio = new AudioContext();
    const wake = () => void audio.resume();
    addEventListener("pointerdown", wake);
    addEventListener("keydown", wake);
    // Not while still muted by the browser (the sounds would pile up), and never over PULSAR's own voice.
    const clear = () => audio.state === "running" && !isSpeaking();

    const chime = () => {
      if (!clear()) return;
      [520, 390].forEach((hz, i) => {
        const osc = audio.createOscillator();
        const gain = audio.createGain();
        osc.frequency.value = hz;
        const start = audio.currentTime + i * 0.32;
        gain.gain.setValueAtTime(0.0001, start);
        gain.gain.exponentialRampToValueAtTime(0.12, start + 0.02);
        gain.gain.exponentialRampToValueAtTime(0.0001, start + 0.4);
        osc.connect(gain).connect(audio.destination);
        osc.start(start);
        osc.stop(start + 0.4);
      });
    };
    const whoop = () => {
      if (!clear()) return;
      const at = audio.currentTime;
      const lowpass = audio.createBiquadFilter();
      lowpass.type = "lowpass";
      lowpass.frequency.value = 1900;
      const gain = audio.createGain();
      const osc = audio.createOscillator();
      osc.type = "square";
      osc.frequency.setValueAtTime(520, at);
      osc.frequency.linearRampToValueAtTime(900, at + 0.65);
      gain.gain.setValueAtTime(0, at);
      gain.gain.linearRampToValueAtTime(0.075, at + 0.03);
      gain.gain.setValueAtTime(0.075, at + 0.68);
      gain.gain.linearRampToValueAtTime(0, at + 0.74);
      osc.connect(gain).connect(lowpass).connect(audio.destination);
      osc.start(at);
      osc.stop(at + 0.75);
    };

    const play = level === "danger" ? whoop : chime;
    play();
    const repeat = level === "danger" ? window.setInterval(play, 900) : 0;
    return () => {
      clearInterval(repeat);
      removeEventListener("pointerdown", wake);
      removeEventListener("keydown", wake);
      void audio.close();
    };
  }, [level, silenced]);
}
