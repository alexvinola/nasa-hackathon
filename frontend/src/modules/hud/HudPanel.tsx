"use client";

import { useState, type ReactNode } from "react";

/** The stack of panels down the left edge of the HUD; panels rendered elsewhere join it through a portal. */
export const LEFT_COLUMN_ID = "hud-left";

/**
 * A HUD panel that folds down to its title, so the camera view is not buried under readouts. The content stays
 * mounted while folded: hotkeys and background checks inside it keep working.
 */
export function HudPanel({
  title,
  defaultOpen = true,
  className = "",
  up = false,
  open: forced,
  onOpenChange,
  children,
  ...rest
}: {
  title: ReactNode;
  defaultOpen?: boolean;
  className?: string;
  /** Unfolds upwards: the title stays put at the bottom and the content opens above it. */
  up?: boolean;
  /** Controlled: lets something else (PULSAR, asked by voice) open or fold the panel. */
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
  children: ReactNode;
} & Record<`data-${string}`, string | boolean>) {
  const [inner, setInner] = useState(defaultOpen);
  const open = forced ?? inner;
  const setOpen = (next: (was: boolean) => boolean) => (onOpenChange ?? setInner)(next(open));
  return (
    <section data-hud-panel {...rest} className={`hud-glass border p-3 text-xs tracking-[0.12em] text-shell/80 backdrop-blur ${up ? "flex flex-col-reverse" : ""} ${className}`}>
      <button type="button" aria-expanded={open} onClick={() => setOpen((was) => !was)} className="pointer-events-auto flex w-full items-center justify-between gap-3 text-left text-pulse">
        <span>{title}</span>
        <span aria-hidden className="border border-pulse/40 px-1.5 leading-tight">{open ? "−" : "+"}</span>
      </button>
      <div hidden={!open} className={up ? "mb-2" : "mt-2"}>{children}</div>
    </section>
  );
}
