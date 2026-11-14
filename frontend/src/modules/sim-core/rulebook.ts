/** The rules and countermeasures as the rules engine lists them (GET /rules, GET /countermeasures): never copied here. */
import type { Status } from "@/modules/voice-ai/verdictApi";

const API = process.env.NEXT_PUBLIC_PULSAR_API ?? "http://localhost:8000";

export type Rule = { id: string; signal: string; status: Status; bodySystems: string[]; countermeasureId: string };
export type Countermeasure = { id: string; title: string; steps: string[] };
export type Rulebook = { rules: Rule[]; countermeasures: Countermeasure[] };

async function get<T>(path: string): Promise<T> {
  const response = await fetch(API + path);
  if (!response.ok) throw new Error(`Backend error ${response.status}`);
  return response.json();
}

export async function fetchRulebook(): Promise<Rulebook> {
  const [rules, countermeasures] = await Promise.all([get<Rule[]>("/rules"), get<Countermeasure[]>("/countermeasures")]);
  return { rules, countermeasures };
}
