"use client";

import { useEffect, useState, type ReactNode } from "react";

/** Colours of the scene for each exercise: the light of the aurora and of the orb. */
export const PALETTE = {
  breathe: { a: "#1fd6c8", b: "#2f6bff", c: "#7a5cff" },
  eyes: { a: "#8f7cff", b: "#3a8dff", c: "#e08cff" },
  body: { a: "#ff9c7a", b: "#7a5cff", c: "#ff5fa2" },
  menu: { a: "#1fd6c8", b: "#7a5cff", c: "#2f6bff" },
} as const;
export type Mood = keyof typeof PALETTE;

// A fixed pseudo-random sprinkle of stars/motes, so the scene looks the same on every render.
const MOTES = Array.from({ length: 70 }, (_, i) => {
  const r = (n: number) => ((Math.sin(i * 91.7 + n * 17.3) + 1) * 5000) % 100;
  return { x: r(1), y: r(2), size: 1 + (r(3) % 3), delay: r(4) / 8, duration: 6 + (r(5) % 10) };
});

const CSS = `
@keyframes relax-drift-a { 0%,100% { transform: translate(-10%,-8%) scale(1); } 50% { transform: translate(14%,10%) scale(1.25); } }
@keyframes relax-drift-b { 0%,100% { transform: translate(12%,10%) scale(1.15); } 50% { transform: translate(-14%,-6%) scale(0.9); } }
@keyframes relax-drift-c { 0%,100% { transform: translate(0,12%) scale(0.95); } 50% { transform: translate(8%,-14%) scale(1.2); } }
@keyframes relax-rise { 0% { transform: translateY(0); opacity: 0; } 15%,85% { opacity: 0.9; } 100% { transform: translateY(-90vh); opacity: 0; } }
@keyframes relax-ripple { 0% { transform: scale(0.55); opacity: 0.55; } 100% { transform: scale(1.9); opacity: 0; } }
@keyframes relax-fill { from { width: 0; } to { width: 100%; } }
@keyframes relax-tunnel { 0% { transform: scale(1); opacity: 0; } 15% { opacity: 1; } 100% { transform: scale(0.08); opacity: 0; } }
@keyframes relax-blink { 0%,40%,100% { transform: scaleY(1); } 50%,60% { transform: scaleY(0.06); } }
@keyframes relax-shoulders { 0%,100% { transform: translateY(0); } 50% { transform: translateY(-26px); } }
@keyframes relax-jaw { 0%,100% { transform: scaleY(0.35); } 50% { transform: scaleY(1.3); } }
@keyframes relax-fist { 0%,100% { transform: scale(0.55); } 50% { transform: scale(1.05); } }
@keyframes relax-glow { 0%,100% { opacity: 0.75; } 50% { opacity: 1; } }
@media (prefers-reduced-motion: reduce) { .relax-anim { animation: none !important; } }
`;

/**
 * The backdrop of the relaxation screen: three slow drifting blurred lights (an aurora), motes rising like bubbles and
 * a vignette, tinted for the exercise. Pure CSS: no canvas, so the laptop's GPU has little to do.
 */
export function RelaxBackdrop({ mood, children }: { mood: Mood; children: ReactNode }) {
  const p = PALETTE[mood];
  const blob = (color: string, anim: string, pos: string, secs: number) => (
    <div
      aria-hidden
      className={`relax-anim absolute h-[70vmax] w-[70vmax] rounded-full opacity-40 blur-[90px] ${pos}`}
      style={{ background: `radial-gradient(circle, ${color}, transparent 65%)`, animation: `${anim} ${secs}s ease-in-out infinite` }}
    />
  );
  return (
    <div className="fixed inset-0 z-50 overflow-hidden bg-[#050818] text-shell">
      <style>{CSS}</style>
      <div className="transition-opacity duration-1000">
        {blob(p.a, "relax-drift-a", "-left-[20vmax] -top-[25vmax]", 26)}
        {blob(p.b, "relax-drift-b", "-right-[25vmax] top-[10vmax]", 32)}
        {blob(p.c, "relax-drift-c", "left-[15vmax] -bottom-[35vmax]", 38)}
      </div>
      {MOTES.map((m, i) => (
        <span
          key={i}
          aria-hidden
          className="relax-anim absolute rounded-full bg-white/80"
          style={{ left: `${m.x}%`, top: `${60 + (m.y % 45)}%`, width: m.size, height: m.size, animation: `relax-rise ${m.duration + 8}s linear ${-m.delay * 4}s infinite` }}
        />
      ))}
      <div aria-hidden className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_center,transparent_35%,rgba(2,4,14,0.75))]" />
      <div className="relative flex h-full flex-col items-center gap-6 p-8 tracking-[0.15em]">{children}</div>
    </div>
  );
}

/**
 * The breathing orb: a luminous core and three halos that follow `scale` (the size the phase is heading to, over
 * `seconds`), with ripples leaving it so the eye has something calm to follow.
 */
export function Orb({ mood, scale, seconds }: { mood: Mood; scale: number; seconds: number }) {
  const p = PALETTE[mood];
  // The size is set one frame after the phase starts, so the orb always travels from where it was (a first phase
  // would otherwise appear already at its end size and never visibly swell).
  const [shown, setShown] = useState(0.45);
  useEffect(() => {
    const id = requestAnimationFrame(() => requestAnimationFrame(() => setShown(scale)));
    return () => cancelAnimationFrame(id);
  }, [scale]);
  const ease = { transform: `scale(${shown})`, transition: `transform ${seconds}s linear` };
  return (
    <div className="relative grid h-[26rem] w-[26rem] place-items-center">
      {[0, 1, 2].map((i) => (
        <span
          key={i}
          aria-hidden
          className="relax-anim absolute h-72 w-72 rounded-full border"
          style={{ borderColor: `${p.a}88`, animation: `relax-ripple 9s ease-out ${i * 3}s infinite` }}
        />
      ))}
      <div aria-hidden className="absolute h-[26rem] w-[26rem] rounded-full blur-2xl" style={{ ...ease, background: `radial-gradient(circle, ${p.a}55, transparent 70%)` }} />
      <div aria-hidden className="absolute h-80 w-80 rounded-full" style={{ ...ease, background: `radial-gradient(circle at 35% 30%, ${p.a}cc, ${p.b}88 55%, ${p.c}44)`, boxShadow: `0 0 90px ${p.a}66, inset 0 0 60px ${p.c}55` }} />
      <div aria-hidden className="relax-anim absolute h-40 w-40 rounded-full blur-xl" style={{ ...ease, background: "radial-gradient(circle, #ffffffcc, transparent 70%)", animation: "relax-glow 5s ease-in-out infinite" }} />
    </div>
  );
}

const STROKE = { fill: "none", stroke: "white", strokeWidth: 3, strokeLinecap: "round", strokeLinejoin: "round" } as const;
const anim = (name: string, secs: number, extra = "ease-in-out infinite") => ({ animation: `${name} ${secs}s ${extra}`, transformBox: "fill-box" as const, transformOrigin: "center" });

/**
 * A visible movement for the exercises that are not breathing: what to do with the eyes, shoulders, jaw or hands,
 * drawn as a simple animated line figure over the orb. `phase` is the message key of the phase, so each phase
 * restarts its own movement.
 */
export function Cue({ phase }: { phase: string }) {
  const body = (() => {
    switch (phase) {
      case "relax.eyes.far": // rings flowing away to a far point
        return (
          <g {...STROKE}>
            {[0, 1, 2].map((i) => <circle key={i} cx="80" cy="80" r="60" style={{ ...anim("relax-tunnel", 3, `ease-out ${-i}s infinite`) }} />)}
            <circle cx="80" cy="80" r="4" fill="white" />
          </g>
        );
      case "relax.eyes.blink": // an eye whose lid closes and opens
        return (
          <g {...STROKE}>
            <g style={anim("relax-blink", 2.4)}>
              <path d="M20 80C45 45 115 45 140 80C115 115 45 115 20 80Z" />
              <circle cx="80" cy="80" r="17" fill="white" />
            </g>
          </g>
        );
      case "relax.eyes.close": // closed lid, resting
        return (
          <g {...STROKE} style={anim("relax-glow", 4)}>
            <path d="M20 72C45 108 115 108 140 72" />
            <path d="M42 96l-8 14M80 105v16M118 96l8 14" />
          </g>
        );
      case "relax.body.shoulders": // shoulders rising to the ears and dropping
        return (
          <g {...STROKE}>
            <circle cx="80" cy="42" r="20" />
            <g style={anim("relax-shoulders", 5)}>
              <path d="M18 128C22 96 50 84 80 84C110 84 138 96 142 128" />
              <path d="M18 128L18 110M142 128L142 110" />
            </g>
          </g>
        );
      case "relax.body.jaw": // the jaw loosening
        return (
          <g {...STROKE}>
            <circle cx="80" cy="76" r="46" />
            <circle cx="64" cy="64" r="4" fill="white" />
            <circle cx="96" cy="64" r="4" fill="white" />
            <ellipse cx="80" cy="102" rx="14" ry="9" style={anim("relax-jaw", 4)} />
          </g>
        );
      case "relax.body.hands": // a hand closing and opening
        return (
          <g {...STROKE}>
            <g style={anim("relax-fist", 3.5)}>
              <ellipse cx="80" cy="96" rx="30" ry="28" />
              {[-52, -26, 0, 26, 52].map((deg) => <path key={deg} d="M80 70V34" transform={`rotate(${deg} 80 96)`} />)}
            </g>
          </g>
        );
      default:
        return null;
    }
  })();
  return body ? (
    <svg aria-hidden viewBox="0 0 160 160" className="pointer-events-none absolute h-52 w-52 drop-shadow-[0_0_14px_rgba(255,255,255,0.6)]">
      {body}
    </svg>
  ) : null;
}
