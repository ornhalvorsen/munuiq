"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { DataTable } from "./data-table";
import { InsightChart } from "./insight-chart";
import {
  askQuestion,
  submitFeedback,
  AskResponse,
} from "@/lib/api/analytics";
import { fetchLookups } from "@/lib/api/lookups";
import { useMention } from "@/components/mentions/use-mention";
import { MentionInput } from "@/components/mentions/mention-input";
import { MentionPopover } from "@/components/mentions/mention-popover";
import type { MentionEntity, MentionTriggerConfig } from "@/components/mentions/types";
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
  X,
} from "lucide-react";

const MODELS = [
  { id: "claude-haiku-4-5-20251001", label: "Haiku" },
  { id: "claude-sonnet-4-5-20250929", label: "Sonnet" },
  { id: "claude-opus-4-6", label: "Opus" },
  { id: "openai:gpt-5.2", label: "GPT-5.2" },
] as const;

const TRIGGERS: MentionTriggerConfig[] = [
  { char: "@", label: "Location", color: "blue", entityType: "location" },
  { char: "$", label: "Product", color: "amber", entityType: "product" },
];

interface ChatEntry {
  response: AskResponse;
  feedbackGiven: "up" | "down" | null;
  feedbackPending: boolean;
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
  const colorMap: Record<string, string> = {
    ollama: "bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-400 border-0 text-[10px]",
    openai: "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/30 dark:text-emerald-400 border-0 text-[10px]",
  };
  const defaultColor = "bg-violet-100 text-violet-800 dark:bg-violet-900/30 dark:text-violet-400 border-0 text-[10px]";
  return (
    <Badge className={colorMap[provider] ?? defaultColor}>
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

function NegativeFeedbackForm({
  onSubmit,
  onCancel,
}: {
  onSubmit: (comment: string) => void;
  onCancel: () => void;
}) {
  const [comment, setComment] = useState("");

  return (
    <div className="flex flex-col gap-2 rounded-md border border-destructive/30 bg-destructive/5 p-3">
      <p className="text-xs font-medium text-muted-foreground">
        What was wrong with this answer?
      </p>
      <textarea
        autoFocus
        rows={2}
        placeholder="e.g. Wrong numbers, missing data, misunderstood question..."
        value={comment}
        onChange={(e) => setComment(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            onSubmit(comment);
          }
          if (e.key === "Escape") onCancel();
        }}
        className="w-full rounded-md border bg-background px-3 py-2 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-ring resize-none"
      />
      <div className="flex items-center gap-2 justify-end">
        <Button
          variant="ghost"
          size="sm"
          className="h-7 text-xs"
          onClick={onCancel}
        >
          <X className="mr-1 h-3 w-3" />
          Cancel
        </Button>
        <Button
          variant="destructive"
          size="sm"
          className="h-7 text-xs"
          onClick={() => onSubmit(comment)}
        >
          <ThumbsDown className="mr-1 h-3 w-3" />
          Submit
        </Button>
      </div>
    </div>
  );
}

export function ChatInterfaceV2() {
  const [sqlModel, setSqlModel] = useState("claude-sonnet-4-5-20250929");
  const [insightModel, setInsightModel] = useState("claude-haiku-4-5-20251001");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [history, setHistory] = useState<ChatEntry[]>([]);
  const [entities, setEntities] = useState<Record<string, MentionEntity[]>>({});

  const mention = useMention({ triggers: TRIGGERS, entities });
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // Load lookups on mount
  useEffect(() => {
    fetchLookups()
      .then(setEntities)
      .catch((err) => console.warn("Failed to load lookups:", err));
  }, []);

  const handleAsk = useCallback(async () => {
    if (mention.isEmpty || loading) return;

    const { plainText, mentions } = mention.getSubmitData();
    if (!plainText.trim()) return;

    setError(null);
    setLoading(true);

    try {
      const resp = await askQuestion(
        plainText.trim(),
        sqlModel,
        insightModel,
        mentions.length > 0 ? mentions : undefined
      );
      setHistory((prev) => [
        { response: resp, feedbackGiven: null, feedbackPending: false, sqlExpanded: false },
        ...prev,
      ]);
      mention.clear();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to get answer");
    } finally {
      setLoading(false);
    }
  }, [mention, loading, sqlModel, insightModel]);

  async function handleFeedback(index: number, feedback: "up" | "down") {
    const entry = history[index];
    if (!entry.response.interaction_id || entry.feedbackGiven) return;

    if (feedback === "down") {
      setHistory((prev) =>
        prev.map((e, i) =>
          i === index ? { ...e, feedbackPending: true } : e
        )
      );
      return;
    }

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

  async function handleSubmitNegativeFeedback(index: number, comment: string) {
    const entry = history[index];
    if (!entry.response.interaction_id) return;

    try {
      await submitFeedback(entry.response.interaction_id, "down", comment || undefined);
      setHistory((prev) =>
        prev.map((e, i) =>
          i === index ? { ...e, feedbackGiven: "down", feedbackPending: false } : e
        )
      );
    } catch {
      // Ignore feedback errors
    }
  }

  function cancelNegativeFeedback(index: number) {
    setHistory((prev) =>
      prev.map((e, i) =>
        i === index ? { ...e, feedbackPending: false } : e
      )
    );
  }

  function toggleSql(index: number) {
    setHistory((prev) =>
      prev.map((e, i) =>
        i === index ? { ...e, sqlExpanded: !e.sqlExpanded } : e
      )
    );
  }

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      mention.handleKeyDown(e);
    },
    [mention.handleKeyDown]
  );

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-4 text-xs">
        <div className="flex items-center gap-1.5">
          <span className="text-muted-foreground font-medium">SQL</span>
          {MODELS.map((m) => (
            <Button
              key={m.id}
              variant={sqlModel === m.id ? "default" : "outline"}
              size="sm"
              onClick={() => setSqlModel(m.id)}
              className="text-xs h-7 px-2"
            >
              {m.label}
            </Button>
          ))}
        </div>
        <div className="flex items-center gap-1.5">
          <span className="text-muted-foreground font-medium">Insight</span>
          {MODELS.map((m) => (
            <Button
              key={m.id}
              variant={insightModel === m.id ? "default" : "outline"}
              size="sm"
              onClick={() => setInsightModel(m.id)}
              className="text-xs h-7 px-2"
            >
              {m.label}
            </Button>
          ))}
        </div>
      </div>

      {/* Mention hint */}
      <div className="text-xs text-muted-foreground">
        Type <kbd className="rounded border bg-muted px-1 py-0.5 font-mono text-[10px]">@</kbd> for locations, <kbd className="rounded border bg-muted px-1 py-0.5 font-mono text-[10px]">$</kbd> for products
      </div>

      <div className="relative flex gap-2">
        <MentionInput
          ref={inputRef}
          segments={mention.segments}
          onInput={mention.handleInput}
          onKeyDown={handleKeyDown}
          disabled={loading}
          placeholder="Ask a question about the restaurant data..."
          onSubmit={handleAsk}
          className="flex-1"
        />
        <MentionPopover
          autocomplete={mention.autocomplete}
          onSelect={mention.selectMention}
          onDismiss={mention.dismissAutocomplete}
          anchorRef={inputRef}
        />
        <Button
          onClick={handleAsk}
          disabled={loading || mention.isEmpty}
        >
          {loading ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Send className="h-4 w-4" />
          )}
        </Button>
      </div>

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
                        disabled={!!entry.feedbackGiven || entry.feedbackPending}
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

                {entry.feedbackPending && (
                  <NegativeFeedbackForm
                    onSubmit={(comment) => handleSubmitNegativeFeedback(idx, comment)}
                    onCancel={() => cancelNegativeFeedback(idx)}
                  />
                )}

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
