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
import { Send, ThumbsUp, ThumbsDown, ChevronDown, ChevronRight, Loader2 } from "lucide-react";

interface ChatEntry {
  response: AskResponse;
  feedbackGiven: "up" | "down" | null;
  sqlExpanded: boolean;
}

export function ChatInterface() {
  const [question, setQuestion] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [history, setHistory] = useState<ChatEntry[]>([]);

  async function handleAsk(e: React.FormEvent) {
    e.preventDefault();
    if (!question.trim() || loading) return;

    setError(null);
    setLoading(true);

    try {
      const resp = await askQuestion(question.trim());
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
        prev.map((e, i) => (i === index ? { ...e, feedbackGiven: feedback } : e))
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
          placeholder="Ask about your restaurant data..."
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          disabled={loading}
          className="flex-1"
        />
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
                <div className="flex items-start justify-between">
                  <p className="font-medium">{r.question}</p>
                  <div className="flex items-center gap-1">
                    {r.cached && (
                      <Badge variant="secondary" className="text-xs">
                        {r.cache_tier === "response"
                          ? "Cached"
                          : r.cache_tier === "common"
                            ? "Common Query"
                            : "SQL Cached"}
                      </Badge>
                    )}
                    <Badge variant="outline" className="text-xs">
                      {r.provider} {r.sql_time_ms}ms
                    </Badge>
                  </div>
                </div>

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
                    className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
                    onClick={() => toggleSql(idx)}
                  >
                    {entry.sqlExpanded ? (
                      <ChevronDown className="h-3 w-3" />
                    ) : (
                      <ChevronRight className="h-3 w-3" />
                    )}
                    SQL
                  </button>

                  <div className="flex items-center gap-1">
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-7 w-7"
                      disabled={!!entry.feedbackGiven}
                      onClick={() => handleFeedback(idx, "up")}
                      style={{
                        opacity: entry.feedbackGiven && entry.feedbackGiven !== "up" ? 0.3 : 1,
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
                        opacity: entry.feedbackGiven && entry.feedbackGiven !== "down" ? 0.3 : 1,
                      }}
                    >
                      <ThumbsDown className="h-3.5 w-3.5" />
                    </Button>
                  </div>
                </div>

                {entry.sqlExpanded && (
                  <pre className="overflow-x-auto rounded-md bg-muted p-3 text-xs">
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
