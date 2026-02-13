"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { DataTable } from "./data-table";
import { InsightChart } from "./insight-chart";
import {
  askQuestion,
  submitFeedback,
  AskResponse,
} from "@/lib/api/analytics";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Send,
  ThumbsUp,
  ThumbsDown,
  ChevronDown,
  ChevronRight,
  Loader2,
  Zap,
  Clock,
  Database,
  Brain,
  Coins,
} from "lucide-react";

const MODELS = [
  { id: "claude-haiku-4-5-20251001", label: "Haiku 4.5", provider: "claude" },
  { id: "claude-sonnet-4-5-20250929", label: "Sonnet 4.5", provider: "claude" },
  { id: "claude-opus-4-6", label: "Opus 4.6", provider: "claude" },
  { id: "ollama:sqlcoder", label: "SQLCoder", provider: "ollama" },
  { id: "ollama:duckdb-nsql", label: "DuckDB-NSQL", provider: "ollama" },
] as const;

interface ChatEntry {
  response: AskResponse;
  feedbackGiven: "up" | "down" | null;
  sqlExpanded: boolean;
}

function formatCost(usd: number): string {
  if (usd < 0.001) return `${(usd * 100).toFixed(3)}c`;
  if (usd < 0.01) return `$${usd.toFixed(4)}`;
  return `$${usd.toFixed(3)}`;
}

function CacheBadge({ tier }: { tier: string }) {
  const labels: Record<string, string> = {
    response: "Cached",
    common: "Common Query",
    sql: "SQL Cached",
  };
  return (
    <Badge className="bg-emerald-100 text-emerald-800 dark:bg-emerald-900/30 dark:text-emerald-400 border-0 text-[10px]">
      <Zap className="mr-0.5 h-2.5 w-2.5" />
      {labels[tier] ?? tier}
    </Badge>
  );
}

function ProviderBadge({ provider }: { provider: string }) {
  const isOllama = provider === "ollama";
  return (
    <Badge
      className={
        isOllama
          ? "bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-400 border-0 text-[10px]"
          : "bg-violet-100 text-violet-800 dark:bg-violet-900/30 dark:text-violet-400 border-0 text-[10px]"
      }
    >
      <Brain className="mr-0.5 h-2.5 w-2.5" />
      {provider}
    </Badge>
  );
}

function TimingBadge({ response }: { response: AskResponse }) {
  const isCachedResponse = response.cache_tier === "response";

  const total =
    (response.sql_time_ms ?? 0) +
    (response.query_time_ms ?? 0) +
    (response.insight_time_ms ?? 0);

  const hasTokens =
    response.input_tokens != null && response.output_tokens != null;
  const totalTokens = hasTokens
    ? response.input_tokens! + response.output_tokens!
    : 0;

  return (
    <div className="flex flex-wrap items-center gap-1.5 text-[10px]">
      {response.provider && <ProviderBadge provider={response.provider} />}
      {response.cache_tier && <CacheBadge tier={response.cache_tier} />}

      {!isCachedResponse && (
        <>
          {response.sql_time_ms != null && (
            <Badge variant="outline" className="gap-0.5 text-[10px] font-normal">
              <Brain className="h-2.5 w-2.5" />
              SQL {response.sql_time_ms}ms
            </Badge>
          )}
          {response.query_time_ms != null && (
            <Badge variant="outline" className="gap-0.5 text-[10px] font-normal">
              <Database className="h-2.5 w-2.5" />
              Query {response.query_time_ms}ms
            </Badge>
          )}
          {response.insight_time_ms != null && (
            <Badge variant="outline" className="gap-0.5 text-[10px] font-normal">
              <Brain className="h-2.5 w-2.5" />
              Insight {response.insight_time_ms}ms
            </Badge>
          )}
          {total > 0 && (
            <Badge variant="outline" className="gap-0.5 text-[10px] font-medium">
              <Clock className="h-2.5 w-2.5" />
              {total}ms
            </Badge>
          )}
        </>
      )}

      {hasTokens && (
        <Badge
          className="bg-green-50 text-green-800 dark:bg-green-900/30 dark:text-green-400 border-0 text-[10px]"
          title={`Input: ${response.input_tokens} tokens | Output: ${response.output_tokens} tokens`}
        >
          <Coins className="mr-0.5 h-2.5 w-2.5" />
          {totalTokens} tok
          {response.estimated_cost_usd != null &&
            ` ~ ${formatCost(response.estimated_cost_usd)}`}
        </Badge>
      )}
    </div>
  );
}

export function ChatInterface() {
  const [question, setQuestion] = useState("");
  const [model, setModel] = useState("claude-sonnet-4-5-20250929");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [history, setHistory] = useState<ChatEntry[]>([]);

  async function handleAsk(e: React.FormEvent) {
    e.preventDefault();
    if (!question.trim() || loading) return;

    setError(null);
    setLoading(true);

    try {
      const resp = await askQuestion(question.trim(), model);
      setHistory((prev) => [
        { response: resp, feedbackGiven: null, sqlExpanded: false },
        ...prev,
      ]);
      setQuestion("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to get answer");
    } finally {
      setLoading(false);
    }
  }

  async function handleFeedback(index: number, feedback: "up" | "down") {
    const entry = history[index];
    if (!entry.response.interaction_id || entry.feedbackGiven) return;

    try {
      await submitFeedback(entry.response.interaction_id, feedback);
      setHistory((prev) =>
        prev.map((e, i) =>
          i === index ? { ...e, feedbackGiven: feedback } : e
        )
      );
    } catch {
      // Ignore feedback errors
    }
  }

  function toggleSql(index: number) {
    setHistory((prev) =>
      prev.map((e, i) =>
        i === index ? { ...e, sqlExpanded: !e.sqlExpanded } : e
      )
    );
  }

  return (
    <div className="space-y-4">
      <form onSubmit={handleAsk} className="flex gap-2">
        <Input
          placeholder="Ask a question about the restaurant data..."
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          disabled={loading}
          className="flex-1"
        />
        <Select value={model} onValueChange={setModel}>
          <SelectTrigger className="w-[140px]">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {MODELS.map((m) => (
              <SelectItem key={m.id} value={m.id}>
                {m.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Button type="submit" disabled={loading || !question.trim()}>
          {loading ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Send className="h-4 w-4" />
          )}
        </Button>
      </form>

      {error && (
        <div className="rounded-md border border-destructive/50 bg-destructive/10 p-3 text-sm text-destructive">
          {error}
        </div>
      )}

      <div className="space-y-4">
        {history.map((entry, idx) => {
          const r = entry.response;
          return (
            <Card key={idx}>
              <CardContent className="space-y-3 pt-4">
                <p className="font-medium">Q: {r.question}</p>

                <TimingBadge response={r} />

                <p className="text-sm text-muted-foreground">{r.insight}</p>

                <InsightChart
                  chart={r.chart}
                  columns={r.columns}
                  data={r.data}
                />

                {r.columns.length > 0 && (
                  <DataTable columns={r.columns} data={r.data} />
                )}

                <div className="flex items-center justify-between">
                  <button
                    className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors"
                    onClick={() => toggleSql(idx)}
                  >
                    {entry.sqlExpanded ? (
                      <ChevronDown className="h-3 w-3" />
                    ) : (
                      <ChevronRight className="h-3 w-3" />
                    )}
                    SQL Query
                  </button>

                  {r.interaction_id && (
                    <div className="flex items-center gap-1">
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-7 w-7"
                        disabled={!!entry.feedbackGiven}
                        onClick={() => handleFeedback(idx, "up")}
                        style={{
                          opacity:
                            entry.feedbackGiven &&
                            entry.feedbackGiven !== "up"
                              ? 0.3
                              : 1,
                        }}
                      >
                        <ThumbsUp className="h-3.5 w-3.5" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-7 w-7"
                        disabled={!!entry.feedbackGiven}
                        onClick={() => handleFeedback(idx, "down")}
                        style={{
                          opacity:
                            entry.feedbackGiven &&
                            entry.feedbackGiven !== "down"
                              ? 0.3
                              : 1,
                        }}
                      >
                        <ThumbsDown className="h-3.5 w-3.5" />
                      </Button>
                    </div>
                  )}
                </div>

                {entry.sqlExpanded && (
                  <pre className="overflow-x-auto rounded-md bg-muted p-3 text-xs font-mono">
                    {r.sql}
                  </pre>
                )}
              </CardContent>
            </Card>
          );
        })}
      </div>
    </div>
  );
}
