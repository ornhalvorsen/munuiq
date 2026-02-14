import { fetchJSON } from "@/lib/api-client";

export interface ChartSpec {
  chart_type: string;
  x_key: string;
  y_key: string;
  title: string;
}

export interface AskResponse {
  question: string;
  sql: string;
  columns: string[];
  data: (string | number | null)[][];
  insight: string;
  chart: ChartSpec;
  model: string;
  interaction_id: string | null;
  provider: string | null;
  sql_time_ms: number | null;
  insight_time_ms: number | null;
  query_time_ms: number | null;
  cached: boolean;
  cache_tier: string | null;
  input_tokens: number | null;
  output_tokens: number | null;
  estimated_cost_usd: number | null;
}

export interface DashboardCard {
  title: string;
  sql: string;
  columns: string[];
  data: (string | number | null)[][];
  insight: string;
  chart: ChartSpec;
}

export interface DashboardResponse {
  cards: DashboardCard[];
  model: string;
  cached: boolean;
}

export async function askQuestion(
  question: string,
  model: string = "claude-sonnet-4-5-20250929",
  insightModel?: string
): Promise<AskResponse> {
  return fetchJSON<AskResponse>("/ask", {
    method: "POST",
    body: JSON.stringify({
      question,
      model,
      insight_model: insightModel ?? undefined,
    }),
  });
}

export async function getDashboard(
  model: string = "claude-sonnet-4-5-20250929"
): Promise<DashboardResponse> {
  return fetchJSON<DashboardResponse>("/dashboard", {
    method: "POST",
    body: JSON.stringify({ model }),
  });
}

export async function submitFeedback(
  interactionId: string,
  feedback: "up" | "down",
  comment?: string
): Promise<void> {
  await fetchJSON("/feedback", {
    method: "POST",
    body: JSON.stringify({
      interaction_id: interactionId,
      feedback,
      ...(comment ? { comment } : {}),
    }),
  });
}
