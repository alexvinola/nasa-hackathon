/** Sends the biometrics block of the contract to the local backend. Nothing is stored. */
import type { Biometrics } from "./faceWorker";

const API = process.env.NEXT_PUBLIC_PULSAR_API ?? "http://localhost:8000";

export async function sendBiometrics(biometrics: Biometrics): Promise<void> {
  const response = await fetch(`${API}/biometrics`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(biometrics),
  }).catch(() => {
    throw new Error(`PULSAR backend is not answering at ${API}`);
  });
  if (!response.ok) throw new Error(`Backend error ${response.status}`);
}
