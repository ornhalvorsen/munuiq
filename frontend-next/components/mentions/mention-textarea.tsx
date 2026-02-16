"use client";

import {
  useState,
  useRef,
  useEffect,
  useMemo,
  forwardRef,
  useImperativeHandle,
} from "react";
import { cn } from "@/lib/utils";
import { ScrollArea } from "@/components/ui/scroll-area";
import type { MentionTriggerConfig, MentionEntity } from "./types";

/* ------------------------------------------------------------------ */
/*  Public API                                                         */
/* ------------------------------------------------------------------ */

export interface MentionTextareaHandle {
  clear: () => void;
  submit: () => void;
  focus: () => void;
}

interface MentionTextareaProps {
  triggers: MentionTriggerConfig[];
  entities: Record<string, MentionEntity[]>;
  onSubmit: (
    text: string,
    mentions: Array<{ type: string; id: string; label: string }>
  ) => void;
  /** Fires on every keystroke so the parent can track isEmpty, etc. */
  onValueChange?: (text: string) => void;
  disabled?: boolean;
  placeholder?: string;
  className?: string;
}

/* ------------------------------------------------------------------ */
/*  Helpers                                                            */
/* ------------------------------------------------------------------ */

/** Scan backward from cursor for a trigger char preceded by whitespace / start.
 *  If multiple triggers match, pick the one closest to the cursor. */
function findActiveTrigger(
  text: string,
  cursor: number,
  triggers: MentionTriggerConfig[]
): { trigger: MentionTriggerConfig; query: string; startPos: number } | null {
  const before = text.slice(0, cursor);

  let best: { trigger: MentionTriggerConfig; query: string; startPos: number } | null = null;

  for (const trig of triggers) {
    const idx = before.lastIndexOf(trig.char);
    if (idx === -1) continue;
    if (idx > 0 && !/\s/.test(before[idx - 1])) continue;

    const query = before.slice(idx + 1);
    if (query.includes("\n")) continue;

    if (!best || idx > best.startPos) {
      best = { trigger: trig, query, startPos: idx };
    }
  }
  return best;
}

function filterEntities(list: MentionEntity[], query: string): MentionEntity[] {
  if (!query) return list.slice(0, 20);
  const q = query.toLowerCase();
  return list
    .filter(
      (e) =>
        e.label.toLowerCase().includes(q) ||
        (e.description && e.description.toLowerCase().includes(q))
    )
    .slice(0, 20);
}

/** Color classes for mention chips by trigger color key */
const MENTION_COLORS: Record<string, string> = {
  blue: "bg-blue-100 dark:bg-blue-500/20 text-blue-700 dark:text-blue-300",
  amber: "bg-amber-100 dark:bg-amber-500/20 text-amber-700 dark:text-amber-300",
  green: "bg-green-100 dark:bg-green-500/20 text-green-700 dark:text-green-300",
  red: "bg-red-100 dark:bg-red-500/20 text-red-700 dark:text-red-300",
};

type Segment = { text: string; mention: boolean; color?: string };

/** Parse text into segments: plain text and mention chips */
function buildSegments(
  text: string,
  mentions: Array<{ type: string; id: string; label: string }>,
  triggers: MentionTriggerConfig[]
): Segment[] {
  if (!text) return [];

  const triggerByType = new Map(triggers.map((t) => [t.entityType, t]));
  const ranges: Array<{ start: number; end: number; color: string }> = [];

  for (const m of mentions) {
    if (!text.includes(m.label)) continue;
    const trig = triggerByType.get(m.type);
    if (!trig) continue;
    const needle = trig.char + m.label;
    let from = 0;
    while (true) {
      const idx = text.indexOf(needle, from);
      if (idx === -1) break;
      if (!ranges.some((r) => idx < r.end && idx + needle.length > r.start)) {
        ranges.push({ start: idx, end: idx + needle.length, color: trig.color });
        break;
      }
      from = idx + 1;
    }
  }

  ranges.sort((a, b) => a.start - b.start);

  const segs: Segment[] = [];
  let pos = 0;
  for (const r of ranges) {
    if (r.start > pos) segs.push({ text: text.slice(pos, r.start), mention: false });
    segs.push({ text: text.slice(r.start, r.end), mention: true, color: r.color });
    pos = r.end;
  }
  if (pos < text.length) segs.push({ text: text.slice(pos), mention: false });

  return segs;
}

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

export const MentionTextarea = forwardRef<MentionTextareaHandle, MentionTextareaProps>(
  function MentionTextarea(
    {
      triggers,
      entities,
      onSubmit,
      onValueChange,
      disabled = false,
      placeholder = "Ask a question...",
      className,
    },
    ref
  ) {
    /* ---- state ---- */
    const [text, setText] = useState("");
    const [mentions, setMentions] = useState<
      Array<{ type: string; id: string; label: string }>
    >([]);
    const [active, setActive] = useState<{
      trigger: MentionTriggerConfig;
      query: string;
      startPos: number;
    } | null>(null);
    const [hlIndex, setHlIndex] = useState(0);

    /* ---- refs ---- */
    const taRef = useRef<HTMLTextAreaElement>(null);
    const mirrorRef = useRef<HTMLDivElement>(null);
    const listRef = useRef<HTMLDivElement>(null);
    const textRef = useRef(text);
    textRef.current = text;
    const mentionsRef = useRef(mentions);
    mentionsRef.current = mentions;
    const onSubmitRef = useRef(onSubmit);
    onSubmitRef.current = onSubmit;
    const onValueChangeRef = useRef(onValueChange);
    onValueChangeRef.current = onValueChange;

    /* ---- derived ---- */
    const results = active
      ? filterEntities(entities[active.trigger.entityType] || [], active.query)
      : [];
    const showDropdown = active !== null;

    const segments = useMemo(
      () => buildSegments(text, mentions, triggers),
      [text, mentions, triggers]
    );
    const hasMentions = segments.some((s) => s.mention);

    /* ---- imperative handle ---- */
    useImperativeHandle(ref, () => ({
      clear() {
        setText("");
        setMentions([]);
        setActive(null);
        setHlIndex(0);
        onValueChangeRef.current?.("");
        if (taRef.current) taRef.current.style.height = "auto";
        requestAnimationFrame(() => taRef.current?.focus());
      },
      submit() {
        const t = textRef.current.trim();
        if (!t) return;
        const live = mentionsRef.current.filter((m) =>
          textRef.current.includes(m.label)
        );
        onSubmitRef.current(t, live);
      },
      focus() {
        taRef.current?.focus();
      },
    }));

    /* ---- callbacks ---- */

    function handleChange(e: React.ChangeEvent<HTMLTextAreaElement>) {
      const val = e.target.value;
      const cursor = e.target.selectionStart ?? val.length;

      setText(val);
      onValueChange?.(val);

      const detected = findActiveTrigger(val, cursor, triggers);
      setActive(detected);
      setHlIndex(0);

      // auto-resize
      const ta = taRef.current;
      if (ta) {
        ta.style.height = "auto";
        ta.style.height = Math.min(ta.scrollHeight, 120) + "px";
      }
    }

    function selectEntity(entity: MentionEntity) {
      if (!active) return;

      const before = text.slice(0, active.startPos);
      const cursor = taRef.current?.selectionStart ?? text.length;
      const after = text.slice(cursor);

      const inserted = active.trigger.char + entity.label + " ";
      const newText = before + inserted + after;
      const newCursor = before.length + inserted.length;

      setText(newText);
      onValueChange?.(newText);
      setMentions((prev) => [
        ...prev,
        { type: entity.type, id: entity.id, label: entity.label },
      ]);
      setActive(null);
      setHlIndex(0);

      requestAnimationFrame(() => {
        const ta = taRef.current;
        if (ta) {
          ta.focus();
          ta.selectionStart = newCursor;
          ta.selectionEnd = newCursor;
          ta.style.height = "auto";
          ta.style.height = Math.min(ta.scrollHeight, 120) + "px";
        }
      });
    }

    function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
      if (showDropdown) {
        switch (e.key) {
          case "ArrowDown":
            e.preventDefault();
            setHlIndex((i) => Math.min(i + 1, results.length - 1));
            return;
          case "ArrowUp":
            e.preventDefault();
            setHlIndex((i) => Math.max(i - 1, 0));
            return;
          case "Enter":
          case "Tab":
            if (results.length > 0) {
              e.preventDefault();
              selectEntity(results[hlIndex]);
              return;
            }
            break;
          case "Escape":
            e.preventDefault();
            setActive(null);
            return;
        }
      }

      // Plain Enter = submit
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        const t = text.trim();
        if (!t) return;
        const live = mentions.filter((m) => text.includes(m.label));
        onSubmit(t, live);
      }
    }

    function syncScroll() {
      if (mirrorRef.current && taRef.current) {
        mirrorRef.current.scrollTop = taRef.current.scrollTop;
      }
    }

    /* ---- effects ---- */

    // Focus on mount
    useEffect(() => {
      if (!disabled) taRef.current?.focus();
    }, [disabled]);

    // Scroll highlighted item into view
    useEffect(() => {
      if (!showDropdown || !listRef.current) return;
      const el = listRef.current.querySelector(
        `[data-idx="${hlIndex}"]`
      ) as HTMLElement | null;
      el?.scrollIntoView({ block: "nearest" });
    }, [hlIndex, showDropdown]);

    /* ---- render ---- */
    return (
      <div className="relative flex-1">
        {/* Mirror overlay — renders text with styled mention bricks */}
        {hasMentions && (
          <div
            ref={mirrorRef}
            aria-hidden
            className="pointer-events-none absolute inset-0 z-[1] overflow-hidden whitespace-pre-wrap break-words rounded-md border border-transparent px-3 py-[7px] text-base leading-[1.5] md:text-sm"
          >
            {segments.map((seg, i) =>
              seg.mention ? (
                <span
                  key={i}
                  className={cn(
                    "rounded-[4px] px-0.5 -mx-[1px]",
                    MENTION_COLORS[seg.color!] ?? MENTION_COLORS.blue
                  )}
                >
                  {seg.text}
                </span>
              ) : (
                <span key={i} className="invisible">
                  {seg.text}
                </span>
              )
            )}
          </div>
        )}

        <textarea
          ref={taRef}
          value={text}
          onChange={handleChange}
          onKeyDown={handleKeyDown}
          onScroll={syncScroll}
          onBlur={() => {
            setTimeout(() => setActive(null), 200);
          }}
          disabled={disabled}
          placeholder={placeholder}
          rows={1}
          className={cn(
            "placeholder:text-muted-foreground dark:bg-input/30 border-input min-h-[36px] w-full min-w-0 rounded-md border bg-transparent px-3 py-1.5 text-base shadow-xs transition-[color,box-shadow] outline-none resize-none md:text-sm",
            "focus-visible:border-ring focus-visible:ring-ring/50 focus-visible:ring-[3px]",
            hasMentions && "text-transparent caret-[var(--foreground)] selection:bg-accent/40",
            disabled && "pointer-events-none cursor-not-allowed opacity-50",
            className
          )}
        />

        {showDropdown && (
          <div className="absolute left-0 top-full z-50 mt-1 w-full max-w-[320px] rounded-md border bg-popover text-popover-foreground shadow-md animate-in fade-in-0 slide-in-from-top-2 duration-100">
            {/* Header */}
            <div className="flex items-center gap-1.5 border-b px-3 py-1.5 text-xs text-muted-foreground">
              <span className="font-mono font-semibold">
                {active!.trigger.char}
              </span>
              <span>{active!.trigger.label}s</span>
              {active!.query && (
                <span className="ml-auto text-[10px] opacity-60">
                  {results.length} results
                </span>
              )}
            </div>

            {/* Items */}
            {results.length === 0 ? (
              <div className="px-3 py-3 text-xs text-muted-foreground">
                {(entities[active!.trigger.entityType] || []).length === 0
                  ? `No ${active!.trigger.label.toLowerCase()}s available`
                  : `No matches for "${active!.query}"`}
              </div>
            ) : (
            <ScrollArea className="max-h-[240px]">
              <div ref={listRef} className="py-1">
                {results.map((entity, idx) => (
                  <button
                    key={entity.id}
                    data-idx={idx}
                    className={cn(
                      "w-full text-left px-3 py-1.5 text-sm cursor-pointer transition-colors",
                      idx === hlIndex
                        ? "bg-accent text-accent-foreground"
                        : "hover:bg-accent/50"
                    )}
                    onMouseDown={(e) => {
                      e.preventDefault();
                      selectEntity(entity);
                    }}
                  >
                    <div className="font-medium">{entity.label}</div>
                    {entity.description && (
                      <div className="text-xs text-muted-foreground truncate">
                        {entity.description}
                      </div>
                    )}
                  </button>
                ))}
              </div>
            </ScrollArea>
            )}
          </div>
        )}
      </div>
    );
  }
);
