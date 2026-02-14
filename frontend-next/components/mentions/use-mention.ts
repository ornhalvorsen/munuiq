"use client";

import { useState, useCallback, useRef } from "react";
import type {
  MentionTriggerConfig,
  MentionEntity,
  Segment,
  AutocompleteState,
  MentionSubmitData,
} from "./types";

interface UseMentionConfig {
  triggers: MentionTriggerConfig[];
  entities: Record<string, MentionEntity[]>; // entityType -> entities
}

interface UseMentionReturn {
  segments: Segment[];
  autocomplete: AutocompleteState;
  handleInput: (plainText: string, cursorOffset: number) => void;
  selectMention: (entity: MentionEntity) => void;
  dismissAutocomplete: () => void;
  handleKeyDown: (e: React.KeyboardEvent) => boolean;
  removeMentionAt: (index: number) => void;
  clear: () => void;
  getSubmitData: () => MentionSubmitData;
  isEmpty: boolean;
  plainText: string;
}

const EMPTY_AUTOCOMPLETE: AutocompleteState = {
  active: false,
  trigger: null,
  query: "",
  results: [],
  highlightIndex: 0,
};

/**
 * Get the plain text representation of a segments array.
 */
function segmentsToPlainText(segments: Segment[]): string {
  return segments
    .map((s) => (s.kind === "text" ? s.text : s.mention.trigger.char + s.mention.entity.label))
    .join("");
}

/**
 * Rebuild segments from new plain text, preserving existing mention segments
 * if their text representation still exists in the new text.
 */
function rebuildSegments(prev: Segment[], newPlainText: string): Segment[] {
  const mentionSegments = prev.filter((s) => s.kind === "mention");

  if (mentionSegments.length === 0) {
    return [{ kind: "text", text: newPlainText }];
  }

  let remaining = newPlainText;
  const newSegments: Segment[] = [];
  let allMentionsFound = true;

  for (const m of mentionSegments) {
    const mentionText = m.mention.trigger.char + m.mention.entity.label;
    const pos = remaining.indexOf(mentionText);
    if (pos === -1) {
      allMentionsFound = false;
      break;
    }
    if (pos > 0) {
      newSegments.push({ kind: "text", text: remaining.slice(0, pos) });
    }
    newSegments.push(m);
    remaining = remaining.slice(pos + mentionText.length);
  }

  if (allMentionsFound) {
    if (remaining || newSegments.length === 0) {
      newSegments.push({ kind: "text", text: remaining });
    }
    return newSegments;
  }

  return [{ kind: "text", text: newPlainText }];
}

/**
 * Find trigger at cursor position by scanning backward from cursor in the
 * current text segment for a trigger char preceded by whitespace or at start.
 */
function detectTrigger(
  text: string,
  cursorInText: number,
  triggers: MentionTriggerConfig[]
): { trigger: MentionTriggerConfig; query: string; triggerPos: number } | null {
  const beforeCursor = text.slice(0, cursorInText);

  for (const trigger of triggers) {
    const lastIdx = beforeCursor.lastIndexOf(trigger.char);
    if (lastIdx === -1) continue;

    // Must be preceded by whitespace or at start of text
    if (lastIdx > 0 && !/\s/.test(beforeCursor[lastIdx - 1])) continue;

    const query = beforeCursor.slice(lastIdx + 1);

    // Query must not contain newlines
    if (query.includes("\n")) continue;

    return { trigger, query, triggerPos: lastIdx };
  }

  return null;
}

/**
 * Find which text segment the cursor is in, and where within that segment.
 */
function findCursorSegment(
  segments: Segment[],
  cursorOffset: number
): { segmentIndex: number; cursorInText: number } | null {
  let charCount = 0;

  for (let i = 0; i < segments.length; i++) {
    const s = segments[i];
    const len =
      s.kind === "text"
        ? s.text.length
        : s.mention.trigger.char.length + s.mention.entity.label.length;
    if (charCount + len >= cursorOffset && s.kind === "text") {
      return { segmentIndex: i, cursorInText: cursorOffset - charCount };
    }
    charCount += len;
  }

  // Cursor at the end — find last text segment
  for (let i = segments.length - 1; i >= 0; i--) {
    if (segments[i].kind === "text") {
      return {
        segmentIndex: i,
        cursorInText: (segments[i] as { kind: "text"; text: string }).text.length,
      };
    }
  }

  return null;
}

/**
 * Filter entities by substring match on label or description.
 */
function filterEntities(
  entities: MentionEntity[],
  query: string
): MentionEntity[] {
  if (!query) return entities.slice(0, 20);
  const q = query.toLowerCase();
  return entities
    .filter(
      (e) =>
        e.label.toLowerCase().includes(q) ||
        (e.description && e.description.toLowerCase().includes(q))
    )
    .slice(0, 20);
}

export function useMention(config: UseMentionConfig): UseMentionReturn {
  const [segments, setSegments] = useState<Segment[]>([
    { kind: "text", text: "" },
  ]);
  const [autocomplete, setAutocomplete] =
    useState<AutocompleteState>(EMPTY_AUTOCOMPLETE);

  // Ref to always have the latest segments (avoids stale closures)
  const segmentsRef = useRef(segments);
  segmentsRef.current = segments;

  // Store the cursor position and trigger info for mention insertion
  const triggerInfoRef = useRef<{
    segmentIndex: number;
    triggerPos: number;
    cursorInText: number;
  } | null>(null);

  const handleInput = useCallback(
    (newPlainText: string, cursorOffset: number) => {
      // 1. Compute new segments (pure, no side effects)
      const newSegments = rebuildSegments(segmentsRef.current, newPlainText);

      // 2. Detect trigger in the new segments
      const cursorInfo = findCursorSegment(newSegments, cursorOffset);

      let newAutocomplete = EMPTY_AUTOCOMPLETE;

      if (cursorInfo) {
        const { segmentIndex, cursorInText } = cursorInfo;
        const seg = newSegments[segmentIndex];

        if (seg.kind === "text") {
          const result = detectTrigger(seg.text, cursorInText, config.triggers);

          if (result) {
            const entities = config.entities[result.trigger.entityType] || [];
            const filtered = filterEntities(entities, result.query);
            triggerInfoRef.current = {
              segmentIndex,
              triggerPos: result.triggerPos,
              cursorInText,
            };
            newAutocomplete = {
              active: true,
              trigger: result.trigger,
              query: result.query,
              results: filtered,
              highlightIndex: 0,
            };
          } else {
            triggerInfoRef.current = null;
          }
        } else {
          triggerInfoRef.current = null;
        }
      } else {
        triggerInfoRef.current = null;
      }

      // 3. Set both states (React batches these in the same event handler)
      setSegments(newSegments);
      setAutocomplete(newAutocomplete);
    },
    [config.triggers, config.entities]
  );

  const selectMention = useCallback(
    (entity: MentionEntity) => {
      if (!autocomplete.trigger || !triggerInfoRef.current) return;

      const trigger = autocomplete.trigger;
      const { segmentIndex, triggerPos, cursorInText } = triggerInfoRef.current;

      setSegments((prev) => {
        const seg = prev[segmentIndex];
        if (seg.kind !== "text") return prev;

        const text = seg.text;
        const before = text.slice(0, triggerPos);
        const after = text.slice(cursorInText);

        const newSegments: Segment[] = [];

        for (let i = 0; i < segmentIndex; i++) {
          newSegments.push(prev[i]);
        }

        if (before) {
          newSegments.push({ kind: "text", text: before });
        }

        newSegments.push({
          kind: "mention",
          mention: { entity, trigger },
        });

        const trailing = after.startsWith(" ") ? after : " " + after;
        newSegments.push({ kind: "text", text: trailing });

        for (let i = segmentIndex + 1; i < prev.length; i++) {
          newSegments.push(prev[i]);
        }

        return newSegments;
      });

      triggerInfoRef.current = null;
      setAutocomplete(EMPTY_AUTOCOMPLETE);
    },
    [autocomplete.trigger]
  );

  const dismissAutocomplete = useCallback(() => {
    triggerInfoRef.current = null;
    setAutocomplete(EMPTY_AUTOCOMPLETE);
  }, []);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent): boolean => {
      if (!autocomplete.active) return false;

      if (e.key === "ArrowDown") {
        e.preventDefault();
        setAutocomplete((prev) => ({
          ...prev,
          highlightIndex: Math.min(
            prev.highlightIndex + 1,
            prev.results.length - 1
          ),
        }));
        return true;
      }

      if (e.key === "ArrowUp") {
        e.preventDefault();
        setAutocomplete((prev) => ({
          ...prev,
          highlightIndex: Math.max(prev.highlightIndex - 1, 0),
        }));
        return true;
      }

      if (e.key === "Enter" || e.key === "Tab") {
        if (autocomplete.results.length > 0) {
          e.preventDefault();
          selectMention(autocomplete.results[autocomplete.highlightIndex]);
          return true;
        }
      }

      if (e.key === "Escape") {
        e.preventDefault();
        dismissAutocomplete();
        return true;
      }

      return false;
    },
    [autocomplete, selectMention, dismissAutocomplete]
  );

  const removeMentionAt = useCallback((index: number) => {
    setSegments((prev) => {
      if (index < 0 || index >= prev.length) return prev;
      if (prev[index].kind !== "mention") return prev;

      const newSegments: Segment[] = [];
      for (let i = 0; i < prev.length; i++) {
        if (i === index) continue;
        const last = newSegments[newSegments.length - 1];
        const curr = prev[i];
        if (last?.kind === "text" && curr.kind === "text") {
          newSegments[newSegments.length - 1] = {
            kind: "text",
            text: last.text + curr.text,
          };
        } else {
          newSegments.push(curr);
        }
      }
      if (newSegments.length === 0) {
        newSegments.push({ kind: "text", text: "" });
      }
      return newSegments;
    });
  }, []);

  const clear = useCallback(() => {
    setSegments([{ kind: "text", text: "" }]);
    setAutocomplete(EMPTY_AUTOCOMPLETE);
    triggerInfoRef.current = null;
  }, []);

  const getSubmitData = useCallback((): MentionSubmitData => {
    const mentions: MentionSubmitData["mentions"] = [];
    let plainText = "";

    for (const seg of segments) {
      if (seg.kind === "text") {
        plainText += seg.text;
      } else {
        plainText += seg.mention.entity.label;
        mentions.push({
          type: seg.mention.entity.type,
          id: seg.mention.entity.id,
          label: seg.mention.entity.label,
        });
      }
    }

    return { plainText: plainText.trim(), mentions };
  }, [segments]);

  const plainText = segmentsToPlainText(segments);
  const isEmpty = segments.every(
    (s) => s.kind === "text" && s.text.trim() === ""
  );

  return {
    segments,
    autocomplete,
    handleInput,
    selectMention,
    dismissAutocomplete,
    handleKeyDown,
    removeMentionAt,
    clear,
    getSubmitData,
    isEmpty,
    plainText,
  };
}
