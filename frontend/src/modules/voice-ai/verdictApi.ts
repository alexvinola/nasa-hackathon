/** The rules engine and the voice turn on the local backend (backend/pulsar). Everything stays on this machine. */
import nominal from "../../../../shared/examples/nominal.json";
import type { Biometrics } from "@/modules/vision-hud/faceWorker";

const API = process.env.NEXT_PUBLIC_PULSAR_API ?? "http://localhost:8000";

export type Status = "GREEN" | "AMBER" | "RED";
export type Factor = { signal: string; value: unknown; threshold: unknown; hazard: string | null; source: string | null; message: string };
export type Decision = {
  status: Status;
  escalation: "SELF_CARE" | "CREW" | "FLIGHT_SURGEON";
  affectedSystems: string[];
  hrpRisk: string | null;
  factors: Factor[];
  countermeasureId: string | null;
};
export type Advice = { decision: Decision; say: string; source: "llm" | "fallback" };
export type Telemetry = typeof nominal;

/**
 * The full contract the engine needs. Only `biometrics` is measured (the camera); sleep, mood, cabin and the PVT
 * keep shared/examples/nominal.json until the judge sliders (G6) and the PVT-B (G3) fill them.
 */
export function telemetryFrom(biometrics: Biometrics): Telemetry {
  return { ...nominal, timestamp: Math.floor(Date.now() / 1000), biometrics } as Telemetry;
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const response = await fetch(API + path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  }).catch(() => {
    throw new Error(`PULSAR backend is not answering at ${API}`);
  });
  if (!response.ok) throw new Error(`Backend error ${response.status}`);
  return response.json();
}

/** The engine's decision alone: deterministic and instant, cheap enough to ask every couple of seconds. */
export const evaluate = (telemetry: Telemetry) => post<Decision>("/rules/evaluate", telemetry);

/** The decision plus the sentence PULSAR speaks (Gemma phrases it): about a second, ask only when it changes. */
export const advise = (telemetry: Telemetry, question = "") => post<Advice>("/voice/advise", { telemetry, question });
