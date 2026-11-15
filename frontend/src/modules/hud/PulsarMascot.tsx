"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { useT } from "@/i18n";
import { PulsarSprite3D, type Mood } from "./PulsarSprite3D";

/** PULSAR (3D model drawn as pixel art) plus its typed speech bubble. */
export function PulsarMascot({
  message,
  mood = "idle",
  heading = 0,
  bpm,
}: {
  message: string;
  mood?: Mood;
  heading?: number;
  /** Heart rate that the chest badge beats to. */
  bpm?: number | null;
}) {
  const t = useT();
  const [typed, setTyped] = useState(0);
  // The X closes the bubble; a new message opens it again.
  const [closed, setClosed] = useState(false);
  useEffect(() => setClosed(false), [message]);

  useEffect(() => {
    setTyped(0);
    const id = setInterval(
      () =>
        setTyped((n) => {
          if (n + 1 >= message.length) clearInterval(id); // done typing: stop ticking
          return Math.min(n + 1, message.length);
        }),
      28,
    );
    return () => clearInterval(id);
  }, [message]);

  // While the text is being typed PULSAR talks, unless it is alerting.
  const acting = mood === "idle" && typed < message.length ? "talk" : mood;
  const tone = mood === "alert" ? "border-red-500" : "border-pulse";

  return (
    <div className="flex items-start gap-3">
      <PulsarSprite3D heading={heading} mood={acting} bpm={bpm} />
      {/* Outside the keyed bubble: a live region must persist and change to be announced. */}
      <p className="sr-only" aria-live="polite">{message}</p>
      {/* No bubble until PULSAR has something to say: nothing it says is scripted. */}
      {message && !closed && (
        <motion.div
          key={message}
          initial={{ opacity: 0, x: -8 }}
          animate={{ opacity: 1, x: 0 }}
          className={`relative mt-10 w-[340px] border-2 bg-space/95 px-4 py-3 pr-9 text-lg leading-snug text-white ${tone}`}
        >
          <button
            type="button"
            onClick={() => setClosed(true)}
            aria-label={t("hud.bubble.close")}
            className="hud-btn absolute right-1 top-1 grid h-6 w-6 place-items-center text-xs"
          >
            ✕
          </button>
          <span aria-hidden>
            {message.slice(0, typed)}
            <span className="hud-blink ml-1 text-pulse">▌</span>
          </span>
        </motion.div>
      )}
    </div>
  );
}
