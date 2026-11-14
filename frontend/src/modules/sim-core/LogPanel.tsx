"use client";

import { useEffect, useRef, useState } from "react";
import { HudPanel } from "@/modules/hud/HudPanel";
import { useHotkey } from "@/modules/hud/useHotkey";

const API = process.env.NEXT_PUBLIC_PULSAR_API ?? "http://localhost:8000";
const POLL_MS = 1000;
const KEEP = 400; // lines kept in the page, as many as the backend keeps
const KEEP_NOISY = 100; // of the requests sent every second or two, which are hidden unless asked for

type LogEvent = { id: number; at: number; kind: string; text: string; noisy?: boolean };

const TONE: Record<string, string> = {
  http: "text-shell/60",
  engine: "text-pulse",
  gemma: "text-orbit",
  voice: "text-emerald-300",
  error: "text-red-400",
};

const clock = (at: number) => new Date(at * 1000).toLocaleTimeString("en-GB", { hour12: false });

/**
 * What the backend is doing right now, read from its in-memory log (`GET /debug/events`): every request with its
 * status and time, the engine's verdicts, how long Gemma took and what it answered, what Whisper heard. Folded by
 * default; L opens it full width. A debugging aid: it shows nothing the backend did not already compute.
 */
export function LogPanel() {
  const [events, setEvents] = useState<LogEvent[]>([]);
  const [wide, setWide] = useState(false);
  const [all, setAll] = useState(false);
  const [down, setDown] = useState(false); // the backend did not answer the last poll
  const last = useRef(0);
  const end = useRef<HTMLDivElement>(null);
  useHotkey("l", () => setWide((was) => !was));

  useEffect(() => {
    let on = true;
    const poll = async () => {
      try {
        const response = await fetch(`${API}/debug/events?after=${last.current}`);
        const body: { events: LogEvent[]; last: number } = await response.json();
        if (!on) return;
        setDown(false);
        if (body.last < last.current) {
          // A restarted backend counts from 1 again: start over and ask for everything on the next poll.
          last.current = 0;
          setEvents([]);
          return;
        }
        last.current = body.last;
        if (!body.events.length) return;
        setEvents((had) => {
          // Two polls can overlap and bring the same events: keep one line per id.
          const lines = [...new Map([...had, ...body.events].map((e) => [e.id, e])).values()];
          const kept = [...lines.filter((e) => !e.noisy).slice(-KEEP), ...lines.filter((e) => e.noisy).slice(-KEEP_NOISY)];
          return kept.sort((a, b) => a.id - b.id);
        });
      } catch {
        if (on) setDown(true);
      }
    };
    void poll();
    const id = setInterval(poll, POLL_MS);
    return () => {
      on = false;
      clearInterval(id);
    };
  }, []);

  const shown = events.filter((event) => all || !event.noisy);
  useEffect(() => {
    end.current?.scrollIntoView({ block: "end" }); // returns a promise in current browsers: it must not be the effect's result
  }, [shown.length, wide]);

  const lines = (
    <ol className="space-y-0.5 font-mono text-[11px] normal-case leading-snug tracking-normal">
      {shown.map((event) => (
        <li key={event.id} className={TONE[event.kind] ?? "text-shell/80"}>
          <span className="text-shell/40">{clock(event.at)}</span> <span className="uppercase">{event.kind}</span> {event.text}
        </li>
      ))}
      {!shown.length && <li className="text-shell/50">{down ? "" : "Nada todavía."}</li>}
      {down && <li className="text-red-400">El backend no responde en {API}.</li>}
      <div ref={end} />
    </ol>
  );
  const controls = (
    <div className="mb-2 flex gap-2">
      <button type="button" aria-pressed={all} onClick={() => setAll((was) => !was)} className="pointer-events-auto border border-shell/40 px-2 py-0.5">
        {all ? "TODAS LAS PETICIONES" : "SIN EL SONDEO DE 1 S"}
      </button>
      <button type="button" onClick={() => setWide((was) => !was)} className="pointer-events-auto border border-shell/40 px-2 py-0.5">
        {wide ? "CERRAR (L)" : "ANCHO (L)"}
      </button>
    </div>
  );

  return (
    <>
      <HudPanel title={`LOG DEL BACKEND (L)${down ? " · CAÍDO" : ""}`} defaultOpen={false}>
        {controls}
        <div className="max-h-48 overflow-y-auto">{lines}</div>
      </HudPanel>
      {wide && (
        <section aria-label="Log del backend" className="fixed inset-x-8 bottom-8 top-1/2 z-40 flex flex-col border border-pulse/50 bg-space/90 p-3 text-xs tracking-[0.12em] text-shell/80 backdrop-blur">
          <div className="flex items-center justify-between text-pulse">
            <span>LOG DEL BACKEND · {shown.length} LÍNEAS</span>
          </div>
          <div className="mt-2">{controls}</div>
          <div className="min-h-0 flex-1 overflow-y-auto">{lines}</div>
        </section>
      )}
    </>
  );
}
