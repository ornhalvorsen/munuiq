"use client";

import {
  useState,
  useRef,
  useEffect,
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

    /* ---- refs (always-fresh values for imperative handle) ---- */
    const taRef = useRef<HTMLTextAreaElement>(null);
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
    // Show dropdown whenever a trigger is active (even with no results)
    const showDropdown = active !== null;

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
            break; // fall through to normal Enter handling
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
        <textarea
          ref={taRef}
          value={text}
          onChange={handleChange}
          onKeyDown={handleKeyDown}
          onBlur={() => {
            // Delay to let dropdown onMouseDown fire first
            setTimeout(() => setActive(null), 200);
          }}
          disabled={disabled}
          placeholder={placeholder}
          rows={1}
          className={cn(
            "placeholder:text-muted-foreground dark:bg-input/30 border-input min-h-[36px] w-full min-w-0 rounded-md border bg-transparent px-3 py-1.5 text-base shadow-xs transition-[color,box-shadow] outline-none resize-none md:text-sm",
            "focus-visible:border-ring focus-visible:ring-ring/50 focus-visible:ring-[3px]",
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
                      e.preventDefault(); // keep textarea focused
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
