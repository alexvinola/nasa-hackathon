"use client";

import { useEffect } from "react";
import { LANGS, restoreLang, setLang, useLang } from "./index";

/** ES | EN switch for the HUD. Restores the saved language once mounted. */
export function LangToggle({ className = "" }: { className?: string }) {
  const lang = useLang();
  useEffect(restoreLang, []);
  return (
    <div role="group" aria-label="Language / Idioma" className={`flex gap-1 text-xs tracking-[0.15em] ${className}`}>
      {LANGS.map((code) => (
        <button
          key={code}
          type="button"
          lang={code}
          aria-pressed={lang === code}
          onClick={() => setLang(code)}
          className={`grid h-8 w-8 place-items-center border backdrop-blur ${lang === code ? "border-pulse bg-pulse/20 text-pulse" : "border-shell/40 bg-space/60 text-shell/70"}`}
        >
          {code.toUpperCase()}
        </button>
      ))}
    </div>
  );
}
