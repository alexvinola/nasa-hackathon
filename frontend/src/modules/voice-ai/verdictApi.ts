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
export function telemetryFrom(biometrics: Biometrics, cabinCo2?: number, radiation?: number): Telemetry {
  const environment = {
    ...nominal.environment,
    ...(cabinCo2 == null ? {} : { cabinCo2_mmHg: cabinCo2 }),
    ...(radiation == null ? {} : { radiation_mSv: radiation }),
  };
  return { ...nominal, timestamp: Math.floor(Date.now() / 1000), biometrics, environment } as Telemetry;
}

/** The limit the rules engine applies to one signal (GET /rules), so the HUD never hard-codes a threshold. */
export async function ruleThreshold(signal: string): Promise<number | null> {
  return (await listRules()).find((rule) => rule.signal === signal)?.threshold ?? null;
}

export type Rule = { id: string; signal: string; threshold: number; status: Status };

/** Every rule the engine applies (GET /rules). */
export async function listRules(): Promise<Rule[]> {
  const response = await fetch(`${API}/rules`);
  if (!response.ok) throw new Error(`Error del backend ${response.status}`);
  return response.json();
}

async function post<T>(path: string, body: unknown, timeoutMs?: number): Promise<T> {
  const response = await fetch(API + path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal: timeoutMs ? AbortSignal.timeout(timeoutMs) : undefined,
  }).catch(() => {
    throw new Error(`El backend de PULSAR no responde en ${API}`);
  });
  if (!response.ok) throw new Error(`Error del backend ${response.status}`);
  return response.json();
}

/** The steps of one countermeasure, as the rules engine lists them (GET /countermeasures/{id}). */
export async function countermeasureSteps(id: string): Promise<string[]> {
  const response = await fetch(`${API}/countermeasures/${encodeURIComponent(id)}`);
  if (!response.ok) throw new Error(`Error del backend ${response.status}`);
  return (await response.json()).steps;
}

/** The engine's decision alone: deterministic and instant, cheap enough to ask every couple of seconds. */
// With a time limit: a request that never answers would otherwise freeze the verdict (and every alarm) for good.
export const evaluate = (telemetry: Telemetry) => post<Decision>("/rules/evaluate", telemetry, 5000);

/** The decision plus the sentence PULSAR speaks (Gemma phrases it): about a second, ask only when it changes. */
export const advise = (telemetry: Telemetry, question = "") => post<Advice>("/voice/advise", { telemetry, question });
