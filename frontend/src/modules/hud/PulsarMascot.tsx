"use client";

import { motion } from "framer-motion";

/** PULSAR as pixel art (80×61 sprite, upscaled with nearest-neighbour) plus its speech bubble. */
export function PulsarMascot({ message }: { message: string }) {
  return (
    <div className="flex items-start gap-3">
      <div className="pulsar-float relative shrink-0 rounded-sm border-2 border-pulse/70 bg-space/60 p-1 shadow-[0_0_18px_rgb(94_242_236/0.35)]">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src="/brand/pulsar-pixel.png" alt="PULSAR" width={160} height={122} className="pixelated block h-[122px] w-[160px]" />
        <span className="absolute -bottom-2 left-2 bg-space px-1 text-[10px] tracking-[0.25em] text-pulse">PULSAR</span>
      </div>
      <motion.div
        key={message}
        initial={{ opacity: 0, x: -8 }}
        animate={{ opacity: 1, x: 0 }}
        className="mt-3 max-w-[260px] border-2 border-pulse/70 bg-space/75 px-3 py-2 text-xs leading-relaxed text-shell"
      >
        {message}
        <span className="hud-blink ml-1 text-pulse">▌</span>
      </motion.div>
    </div>
  );
}
