import { useState } from "react";
import { askQuestion, submitFeedback } from "../api/client";
import type { AskResponse, ModelId } from "../types";
import DataTable from "./DataTable";
import InsightChart from "./InsightChart";

interface HistoryEntry {
  response: AskResponse;
  feedback: "up" | "down" | null;
}

function FeedbackButtons({
  interactionId,
  feedback,
  onFeedback,
}: {
  interactionId?: string;
  feedback: "up" | "down" | null;
  onFeedback: (fb: "up" | "down") => void;
}) {
  if (!interactionId) return null;
  return (
    <div style={{ display: "flex", gap: 4, marginTop: 8 }}>
      <button
        onClick={() => onFeedback("up")}
        disabled={feedback !== null}
        style={{
          background: "none",
          border: "1px solid #e5e7eb",
          borderRadius: 4,
          padding: "2px 8px",
          cursor: feedback !== null ? "default" : "pointer",
          opacity: feedback === "down" ? 0.3 : 1,
          fontSize: 16,
        }}
        title="Good result"
      >
        👍
      </button>
      <button
        onClick={() => onFeedback("down")}
        disabled={feedback !== null}
        style={{
          background: "none",
          border: "1px solid #e5e7eb",
          borderRadius: 4,
          padding: "2px 8px",
          cursor: feedback !== null ? "default" : "pointer",
          opacity: feedback === "up" ? 0.3 : 1,
          fontSize: 16,
        }}
        title="Bad result"
      >
        👎
      </button>
    </div>
  );
}

function CacheBadge({ tier }: { tier: string }) {
  const labels: Record<string, string> = {
    response: "Cached",
    common: "Common Query",
    sql: "SQL Cached",
  };
  return (
    <span
      style={{
        background: "#d1fae5",
        color: "#065f46",
        padding: "1px 6px",
        borderRadius: 4,
        fontWeight: 500,
      }}
    >
      {labels[tier] ?? tier}
    </span>
  );
}

function formatCost(usd: number): string {
  if (usd < 0.001) return `$${(usd * 100).toFixed(3)}c`;
  if (usd < 0.01) return `$${usd.toFixed(4)}`;
  return `$${usd.toFixed(3)}`;
}

function TimingBadge({ response }: { response: AskResponse }) {
  const isCachedResponse = response.cache_tier === "response";

  const parts: string[] = [];
  if (!isCachedResponse) {
    if (response.sql_time_ms != null) parts.push(`SQL ${response.sql_time_ms}ms`);
    if (response.query_time_ms != null) parts.push(`Query ${response.query_time_ms}ms`);
    if (response.insight_time_ms != null) parts.push(`Insight ${response.insight_time_ms}ms`);
  }

  const total =
    (response.sql_time_ms ?? 0) +
    (response.query_time_ms ?? 0) +
    (response.insight_time_ms ?? 0);

  const hasTokens = response.input_tokens != null && response.output_tokens != null;

  return (
    <div
      style={{
        display: "flex",
        gap: 8,
        fontSize: 11,
        color: "#9ca3af",
        marginBottom: 8,
        flexWrap: "wrap",
        alignItems: "center",
      }}
    >
      {response.provider && (
        <span
          style={{
            background: response.provider === "ollama" ? "#fef3c7" : "#ede9fe",
            color: response.provider === "ollama" ? "#92400e" : "#6d28d9",
            padding: "1px 6px",
            borderRadius: 4,
            fontWeight: 500,
          }}
        >
          {response.provider}
        </span>
      )}
      {response.cache_tier && <CacheBadge tier={response.cache_tier} />}
      {parts.map((p) => (
        <span key={p}>{p}</span>
      ))}
      {!isCachedResponse && parts.length > 0 && (
        <span style={{ fontWeight: 500 }}>Total {total}ms</span>
      )}
      {hasTokens && (
        <span
          style={{
            background: "#f0fdf4",
            color: "#166534",
            padding: "1px 6px",
            borderRadius: 4,
            fontWeight: 500,
          }}
          title={`Input: ${response.input_tokens} tokens | Output: ${response.output_tokens} tokens`}
        >
          {response.input_tokens! + response.output_tokens!} tok
          {response.estimated_cost_usd != null && ` ~ ${formatCost(response.estimated_cost_usd)}`}
        </span>
      )}
    </div>
  );
}

export default function Chat({ model }: { model: ModelId }) {
  const [question, setQuestion] = useState("");
  const [history, setHistory] = useState<HistoryEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const q = question.trim();
    if (!q || loading) return;

    setLoading(true);
    setError("");

    try {
      const res = await askQuestion(q, model);
      setHistory((prev) => [{ response: res, feedback: null }, ...prev]);
      setQuestion("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setLoading(false);
    }
  };

  const handleFeedback = async (index: number, fb: "up" | "down") => {
    const entry = history[index];
    const id = entry.response.interaction_id;
    if (!id) return;
    try {
      await submitFeedback(id, fb);
      setHistory((prev) =>
        prev.map((e, i) => (i === index ? { ...e, feedback: fb } : e))
      );
    } catch {
      // Silently ignore feedback errors
    }
  };

  return (
    <div>
      <form onSubmit={handleSubmit} style={{ display: "flex", gap: 8, marginBottom: 16 }}>
        <input
          type="text"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="Ask a question about the restaurant data..."
          style={{
            flex: 1,
            padding: "8px 12px",
            fontSize: 14,
            border: "1px solid #ccc",
            borderRadius: 6,
          }}
          disabled={loading}
        />
        <button
          type="submit"
          disabled={loading || !question.trim()}
          style={{
            padding: "8px 20px",
            fontSize: 14,
            background: loading ? "#999" : "#4f46e5",
            color: "#fff",
            border: "none",
            borderRadius: 6,
            cursor: loading ? "not-allowed" : "pointer",
          }}
        >
          {loading ? "Thinking..." : "Ask"}
        </button>
      </form>

      {error && (
        <div
          style={{
            color: "#dc2626",
            background: "#fef2f2",
            padding: 12,
            borderRadius: 6,
            marginBottom: 12,
          }}
        >
          {error}
        </div>
      )}

      {history.map((entry, i) => (
        <div
          key={i}
          style={{
            border: "1px solid #e5e7eb",
            borderRadius: 8,
            padding: 16,
            marginBottom: 12,
          }}
        >
          <p style={{ fontWeight: 600, marginBottom: 8 }}>Q: {entry.response.question}</p>
          <TimingBadge response={entry.response} />
          <p style={{ color: "#374151", marginBottom: 8 }}>{entry.response.insight}</p>
          <details style={{ marginBottom: 8 }}>
            <summary style={{ cursor: "pointer", fontSize: 13, color: "#6b7280" }}>
              SQL Query
            </summary>
            <pre
              style={{
                background: "#f3f4f6",
                padding: 12,
                borderRadius: 4,
                fontSize: 12,
                overflowX: "auto",
                marginTop: 4,
              }}
            >
              {entry.response.sql}
            </pre>
          </details>
          <InsightChart
            chart={entry.response.chart}
            columns={entry.response.columns}
            data={entry.response.data}
          />
          <DataTable columns={entry.response.columns} data={entry.response.data} />
          <FeedbackButtons
            interactionId={entry.response.interaction_id}
            feedback={entry.feedback}
            onFeedback={(fb) => handleFeedback(i, fb)}
          />
        </div>
      ))}
    </div>
  );
}
