"use client";

import { PulsarMascot } from "./PulsarMascot";
import { useWebcam, type CamState } from "./useWebcam";

const CAM_LABEL: Record<CamState, string> = {
  starting: "CAM · STARTING",
  live: "CAM · LIVE",
  denied: "CAM · PERMISSION DENIED",
  unavailable: "CAM · NOT AVAILABLE",
};

function Corner({ className }: { className: string }) {
  return <span className={`absolute h-8 w-8 border-pulse/80 ${className}`} />;
}

/** Full-screen camera with the HUD layered on top. Placeholder readouts until the verticals plug in. */
export function Hud() {
  const { videoRef, state } = useWebcam();

  return (
    <main className="relative h-screen w-screen overflow-hidden bg-space">
      <video ref={videoRef} muted playsInline className="absolute inset-0 h-full w-full -scale-x-100 object-cover" />
      {state !== "live" && (
        <div className="absolute inset-0 grid place-items-center bg-[radial-gradient(ellipse_at_center,var(--color-space-lift),var(--color-space))] text-sm tracking-widest text-orbit">
          {CAM_LABEL[state]}
        </div>
      )}

      <div className="hud-scanlines pointer-events-none absolute inset-0" />
      <div className="hud-vignette pointer-events-none absolute inset-0" />

      <div className="pointer-events-none absolute inset-4">
        <Corner className="left-0 top-0 border-l-2 border-t-2" />
        <Corner className="right-0 top-0 border-r-2 border-t-2" />
        <Corner className="bottom-0 left-0 border-b-2 border-l-2" />
        <Corner className="bottom-0 right-0 border-b-2 border-r-2" />
      </div>

      <div className="absolute left-8 top-8">
        <PulsarMascot message="Hi, I'm PULSAR. I'm watching over you." />
      </div>

      <div className="absolute right-8 top-8 text-right text-[11px] tracking-[0.2em] text-pulse">
        <div className={state === "live" ? "" : "text-orbit"}>● {CAM_LABEL[state]}</div>
        <div className="mt-1 text-shell/70">OFFLINE · LOCAL ONLY</div>
      </div>

      <div className="absolute inset-x-8 bottom-8 flex items-end justify-between text-[11px] tracking-[0.2em] text-shell/70">
        <span>PULSAR HUD · v0.1</span>
        <span className="text-orbit">NOT A MEDICAL DEVICE</span>
      </div>
    </main>
  );
}
