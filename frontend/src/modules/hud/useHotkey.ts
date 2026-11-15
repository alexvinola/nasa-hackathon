"use client";

import { useEffect, useRef } from "react";

type Field = HTMLInputElement | HTMLTextAreaElement;
/** What a field does with the key: "free" fires it on its own, "ctrl" needs Ctrl held (the field uses the plain key), false ignores it. */
export type FieldRule = "free" | "ctrl" | false;

/**
 * Runs `onDown` when `key` is pressed anywhere on the HUD, and `onUp` when it is released (for hold-to-talk).
 * `key` is KeyboardEvent.key in lower case (" " for the space bar). Ignored with a modifier held (Ctrl only where a
 * field's rule asks for it) and on auto-repeat, and ignored while typing in a text field unless `inField` says
 * otherwise. `onUp` always fires on release, so a hold can never get stuck.
 */
export function useHotkey(key: string, onDown: () => void, onUp?: () => void, inField?: (field: Field) => FieldRule) {
  const handlers = useRef({ onDown, onUp });
  handlers.current = { onDown, onUp };
  const rule = useRef(inField);
  rule.current = inField;

  useEffect(() => {
    const mine = (e: KeyboardEvent) => {
      if (e.key.toLowerCase() !== key || e.metaKey || e.altKey) return false;
      if (!(e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement)) return !e.ctrlKey;
      const how = rule.current?.(e.target) ?? false;
      return how === "free" ? !e.ctrlKey : how === "ctrl" && e.ctrlKey;
    };
    const down = (e: KeyboardEvent) => {
      if (!mine(e)) return;
      e.preventDefault(); // the key belongs to the shortcut: no page scroll, no click on a focused button
      if (!e.repeat) handlers.current.onDown();
    };
    const up = (e: KeyboardEvent) => {
      if (e.key.toLowerCase() === key) handlers.current.onUp?.();
    };
    addEventListener("keydown", down);
    addEventListener("keyup", up);
    return () => {
      removeEventListener("keydown", down);
      removeEventListener("keyup", up);
    };
  }, [key]);
}
