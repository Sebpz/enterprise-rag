import type { EvalRun } from "./types";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const API_KEY = "dev-key-local";

const headers = {
  "Content-Type": "application/json",
  "X-API-Key": API_KEY,
};

export async function fetchEvalRuns(): Promise<EvalRun[]> {
  const res = await fetch(`${API_URL}/v1/evals`, { headers });
  if (!res.ok) throw new Error(`Failed to fetch evals: ${res.status}`);
  return res.json();
}

export async function submitFeedback(
  traceId: string,
  rating: 1 | -1,
  comment?: string
): Promise<void> {
  await fetch(`${API_URL}/v1/feedback`, {
    method: "POST",
    headers,
    body: JSON.stringify({ trace_id: traceId, rating, comment }),
  });
}

export { API_URL, API_KEY };
