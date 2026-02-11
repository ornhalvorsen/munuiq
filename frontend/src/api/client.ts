import type { AskResponse, DashboardResponse, SchemaResponse, HealthResponse, ModelId } from "../types";

async function fetchJSON<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, init);
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(body.detail || res.statusText);
  }
  return res.json();
}

export function getHealth(): Promise<HealthResponse> {
  return fetchJSON("/api/health");
}

export function getSchema(): Promise<SchemaResponse> {
  return fetchJSON("/api/schema");
}

export function askQuestion(question: string, model: ModelId): Promise<AskResponse> {
  return fetchJSON("/api/ask", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, model }),
  });
}

export function submitFeedback(interactionId: string, feedback: "up" | "down"): Promise<{ status: string }> {
  return fetchJSON("/api/feedback", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ interaction_id: interactionId, feedback }),
  });
}

export function getDashboard(model: ModelId): Promise<DashboardResponse> {
  return fetchJSON("/api/dashboard", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ model }),
  });
}
