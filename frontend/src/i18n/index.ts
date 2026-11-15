import { useSyncExternalStore } from "react";
import { messages, type Key } from "./messages";

/**
 * Two languages, no library. The default comes from NEXT_PUBLIC_LANG ("es" or "en", else "es"); the astronaut can
 * switch it at runtime (LangToggle) and the choice is remembered in the browser. Strings that travel to the backend
 * or are compared there (status ids, signals, spot names) are never translated: only what is shown.
 */
export type Lang = "es" | "en";
export const LANGS: Lang[] = ["es", "en"];
export type { Key };

const STORAGE = "pulsar-lang";
export const DEFAULT_LANG: Lang = process.env.NEXT_PUBLIC_LANG === "en" ? "en" : "es";

let current: Lang = DEFAULT_LANG;
const listeners = new Set<() => void>();

export const getLang = () => current;

export function setLang(lang: Lang) {
  if (lang === current) return;
  current = lang;
  try {
    localStorage.setItem(STORAGE, lang);
  } catch {
    // private window or blocked storage: the choice just lasts until reload
  }
  if (typeof document !== "undefined") document.documentElement.lang = lang;
  listeners.forEach((listener) => listener());
}

/** Applies the saved choice. Call once on the client after hydration, so server and client first render the same. */
export function restoreLang() {
  try {
    const saved = localStorage.getItem(STORAGE);
    if (saved === "es" || saved === "en") setLang(saved);
  } catch {
    // no storage: keep the default
  }
  if (typeof document !== "undefined") document.documentElement.lang = current;
}

/** The text for `key` in the current language, with `{name}` placeholders filled from `vars`. */
export function t(key: Key, vars?: Record<string, string | number>): string {
  const text = messages[current][key] ?? messages[DEFAULT_LANG][key] ?? key;
  return vars ? text.replace(/\{(\w+)\}/g, (whole, name) => (name in vars ? String(vars[name]) : whole)) : text;
}

/** The current language, re-rendering the component when it changes. */
export function useLang(): Lang {
  return useSyncExternalStore((listener) => (listeners.add(listener), () => listeners.delete(listener)), getLang, () => DEFAULT_LANG);
}

/** `t` for components: subscribing to the language is what makes them redraw when it changes. */
export function useT() {
  useLang();
  return t;
}
