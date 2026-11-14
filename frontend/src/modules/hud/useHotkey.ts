"use client";

import { useEffect, useRef } from "react";

/**
 * Runs `onDown` when `key` is pressed anywhere on the HUD, and `onUp` when it is released (for hold-to-talk).
 * `key` is KeyboardEvent.key in lower case (" " for the space bar). Ignored while typing in a text field, with a
 * modifier held, and on auto-repeat.
 */
export function useHotkey(key: string, onDown: () => void, onUp?: () => void) {
  const handlers = useRef({ onDown, onUp });
  handlers.current = { onDown, onUp };

  useEffect(() => {
    const mine = (e: KeyboardEvent) =>
      e.key.toLowerCase() === key &&
      !e.ctrlKey && !e.metaKey && !e.altKey &&
      !(e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement);
    const down = (e: KeyboardEvent) => {
      if (!mine(e)) return;
      e.preventDefault(); // the key belongs to the shortcut: no page scroll, no click on a focused button
      if (!e.repeat) handlers.current.onDown();
    };
    const up = (e: KeyboardEvent) => {
      if (mine(e)) handlers.current.onUp?.();
    };
    addEventListener("keydown", down);
    addEventListener("keyup", up);
    return () => {
      removeEventListener("keydown", down);
      removeEventListener("keyup", up);
    };
  }, [key]);
}
