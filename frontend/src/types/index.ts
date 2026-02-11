export type ModelId =
  | "claude-opus-4-6"
  | "claude-sonnet-4-5-20250929"
  | "claude-haiku-4-5-20251001"
  | "ollama:sqlcoder"
  | "ollama:duckdb-nsql";

export interface ModelOption {
  id: ModelId;
  label: string;
  color: string;
  provider: "claude" | "ollama";
}

export const MODELS: ModelOption[] = [
  { id: "claude-haiku-4-5-20251001", label: "Haiku 4.5", color: "#059669", provider: "claude" },
  { id: "claude-sonnet-4-5-20250929", label: "Sonnet 4.5", color: "#2563eb", provider: "claude" },
  { id: "claude-opus-4-6", label: "Opus 4.6", color: "#7c3aed", provider: "claude" },
  { id: "ollama:sqlcoder", label: "SQLCoder", color: "#d97706", provider: "ollama" },
  { id: "ollama:duckdb-nsql", label: "DuckDB-NSQL", color: "#dc2626", provider: "ollama" },
];

export interface ChartSpec {
  chart_type: "bar" | "line" | "none";
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
  provider?: string;
  sql_time_ms?: number;
  insight_time_ms?: number;
  query_time_ms?: number;
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

export interface SchemaResponse {
  tables: Record<string, { column: string; type: string; nullable: boolean }[]>;
  table_count: number;
}

export interface HealthResponse {
  status: string;
  tables: number;
  models: string[];
  ollama_available: boolean;
  ollama_models: string[];
}
