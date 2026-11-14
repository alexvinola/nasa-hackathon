"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { PulsarSprite3D, type Mood } from "./PulsarSprite3D";

/** PULSAR (3D model drawn as pixel art) plus its typed speech bubble. */
export function PulsarMascot({
  message,
  mood = "idle",
  heading = 0,
  mock = false,
}: {
  message: string;
  mood?: Mood;
  heading?: number;
  mock?: boolean;
}) {
  const [typed, setTyped] = useState(0);

  useEffect(() => {
    setTyped(0);
    const id = setInterval(() => setTyped((n) => Math.min(n + 1, message.length)), 28);
    return () => clearInterval(id);
  }, [message]);

  // While the text is being typed PULSAR talks, unless it is alerting.
  const acting = mood === "idle" && typed < message.length ? "talk" : mood;
  const tone = mood === "alert" ? "border-orbit" : "border-pulse/70";

  return (
    <div className="flex items-start gap-3">
      <PulsarSprite3D heading={heading} mood={acting} />
      <motion.div
        key={message}
        initial={{ opacity: 0, x: -8 }}
        animate={{ opacity: 1, x: 0 }}
        className={`relative mt-10 w-[260px] border-2 bg-space/75 px-3 py-2 text-xs leading-relaxed text-shell ${tone}`}
      >
        {mock && <span className="absolute -top-2 right-2 bg-space px-1 text-[9px] tracking-[0.25em] text-orbit">MOCK</span>}
        <p className="sr-only" aria-live="polite">{message}</p>
        <span aria-hidden>
          {message.slice(0, typed)}
          <span className="hud-blink ml-1 text-pulse">▌</span>
        </span>
      </motion.div>
    </div>
  );
}
