"use client";

import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { PulsarMascot } from "./PulsarMascot";
import { useHotkey } from "./useHotkey";
import { FALSE_START_MS, FOREPERIOD_MS, LAPSE_MS, NO_RESPONSE_MS, PASS_RATIO, TRIALS, isGood, score, type Reaction } from "./reactionScore";

type Phase = "ready" | "wait" | "go" | "done";

const NEEDED = Math.ceil(TRIALS * PASS_RATIO);

/**
 * The reaction check an alarm asks for before it stops, on the whole screen with PULSAR in front: react to three
 * stimuli with ENTER or a click. ESC leaves it at any point, with the alarm still ringing unless it was passed. Passing it acknowledges the alarm; failing it tells the astronaut what to do
 * instead. It never changes the engine's verdict. PULSAR's lines here are the test's own instructions and results,
 * not health advice: that still comes only from the rules engine (`steps`).
 */
export function ReactionTest({
  steps,
  onAcknowledge,
  onClose,
}: {
  /** The countermeasure the rules engine chose, shown when the test is failed. */
  steps: string[];
  onAcknowledge: () => void;
  onClose: () => void;
}) {
  const [phase, setPhase] = useState<Phase>("ready");
  const [reactions, setReactions] = useState<Reaction[]>([]);
  const shownAt = useRef(0);
  const result = score(reactions);

  const record = (ms: Reaction) => {
    const next = [...reactions, ms];
    setReactions(next);
    setPhase(next.length >= TRIALS ? "done" : "wait");
  };

  // Timed from the moment the lit box is on the page; a layout effect, so it is set before any key can arrive.
  useLayoutEffect(() => {
    if (phase === "go") shownAt.current = performance.now();
  }, [phase]);

  // One timer per stimulus: the random wait before it, then how long it stays up unanswered.
  useEffect(() => {
    if (phase !== "wait" && phase !== "go") return;
    const [min, max] = FOREPERIOD_MS;
    const id =
      phase === "wait"
        ? setTimeout(() => setPhase("go"), min + Math.random() * (max - min))
        : setTimeout(() => record(null), NO_RESPONSE_MS);
    return () => clearTimeout(id);
  }, [phase, reactions.length]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (phase === "done" && result.passed) onAcknowledge();
  }, [phase]); // eslint-disable-line react-hooks/exhaustive-deps

  const restart = () => {
    setReactions([]);
    setPhase("wait");
  };
  const react = () => {
    if (phase === "ready") restart();
    else if (phase === "wait") record(null); // before the stimulus: a false start
    else if (phase === "go") record(Math.round(performance.now() - shownAt.current));
    else if (result.passed) onClose();
    else restart();
  };
  useHotkey("enter", react);
  useHotkey("escape", onClose);

  const last = reactions.at(-1);
  const failed = phase === "done" && !result.passed;
  const says =
    phase === "ready"
      ? "Test de reacción. Pulsa ENTER o haz clic en el recuadro grande en cuanto se ilumine."
      : phase !== "done"
        ? last === undefined
          ? "Espera a la luz…"
          : last === null
            ? "Fallo: demasiado pronto o sin respuesta."
            : isGood(last)
              ? `Bien: ${last} ms.`
              : `${last} ms no cuenta.`
        : result.passed
          ? `Superado: ${result.good} de ${TRIALS} buenas, ${result.meanMs} ms de media. Alarma detenida.`
          : `No superado: ${result.good} de ${TRIALS} buenas, necesitabas ${NEEDED}. Haz lo que dice la lista.`;

  return (
    <div role="dialog" aria-modal="true" aria-label="Test de reacción" className="fixed inset-0 z-50 flex flex-col items-center gap-6 bg-space p-8 tracking-[0.15em]">
      <PulsarMascot message={says} mood={failed ? "alert" : "idle"} />

      {phase !== "done" ? (
        <>
          <button
            type="button"
            autoFocus
            onPointerDown={react}
            className={`grid min-h-0 w-full flex-1 place-items-center border-4 text-6xl font-bold ${phase === "go" ? "border-pulse bg-pulse text-space" : "border-shell/40 text-shell/70"}`}
          >
            {phase === "ready" ? "ENTER O CLIC PARA EMPEZAR" : phase === "go" ? "YA" : "ESPERA…"}
          </button>
          <p className="max-w-4xl text-center text-base normal-case leading-snug tracking-normal text-shell">
            Estímulo {Math.min(reactions.length + 1, TRIALS)} de {TRIALS}. Una reacción cuenta si tarda entre{" "}
            {FALSE_START_MS} y {LAPSE_MS} ms: menos de {FALSE_START_MS} ms es una suposición, {LAPSE_MS} ms o más es un
            lapso (criterio PVT-B). Pulsar antes de la luz, o no responder en {NO_RESPONSE_MS / 1000} s, es un fallo.
            Necesitas {NEEDED} de {TRIALS} para detener la alarma.
          </p>
          <button type="button" onClick={onClose} className="text-sm text-shell/70 underline">
            SALIR (ESC) · LA ALARMA SIGUE SONANDO
          </button>
        </>
      ) : result.passed ? (
        <div role="status" className="grid w-full flex-1 place-items-center border-4 border-pulse text-center text-pulse">
          <div>
            <h2 className="text-5xl font-bold">TEST SUPERADO · ALARMA DETENIDA</h2>
            <p className="mt-4 text-xl text-shell">
              {result.good} / {TRIALS} REACCIONES BUENAS · MEDIA {result.meanMs} ms
            </p>
            <button type="button" onClick={onClose} className="mt-8 border-2 border-pulse px-8 py-3 text-lg font-bold">
              CERRAR (ENTER O ESC)
            </button>
          </div>
        </div>
      ) : (
        <div role="alert" className="grid w-full flex-1 place-items-center overflow-y-auto border-4 border-red-500 text-center text-red-200">
          <div className="max-w-3xl p-6">
            <h2 className="text-4xl font-bold">TEST NO SUPERADO · {result.good} / {TRIALS} REACCIONES BUENAS</h2>
            <p className="mt-6 text-sm text-shell/90">HAZ ESTO AHORA</p>
            <ol className="mt-2 list-inside list-decimal space-y-2 text-2xl normal-case leading-snug tracking-normal text-white">
              <li>Comprueba tu pulso.</li>
              {steps.length ? steps.map((step) => <li key={step}>{step}</li>) : <li>Deja lo que estás haciendo y ve a dormir.</li>}
            </ol>
            <button
              type="button"
              onClick={() => {
                onAcknowledge();
                onClose();
              }}
              className="mt-8 w-full border-2 border-red-400 bg-red-600 px-3 py-3 text-lg font-bold text-white"
            >
              VOY A DESCANSAR · DETENER LA ALARMA
            </button>
            <button type="button" onClick={restart} className="mt-3 w-full border-2 border-shell/40 px-3 py-3 text-lg text-shell">
              REINTENTAR (ENTER)
            </button>
            <button type="button" onClick={onClose} className="mt-3 text-sm text-shell/70 underline">
              SALIR (ESC) · LA ALARMA SIGUE SONANDO
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
