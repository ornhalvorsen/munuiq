"use client";

import { useRef, useCallback, useEffect, forwardRef } from "react";
import { cn } from "@/lib/utils";
import type { Segment } from "./types";

interface MentionInputProps {
  segments: Segment[];
  onInput: (plainText: string, cursorOffset: number) => void;
  onKeyDown: (e: React.KeyboardEvent) => void;
  disabled?: boolean;
  placeholder?: string;
  className?: string;
  onSubmit?: () => void;
}

/**
 * Plain text representation of segments (what the user sees in the textarea).
 */
function segmentsToText(segments: Segment[]): string {
  return segments
    .map((s) =>
      s.kind === "text"
        ? s.text
        : s.mention.trigger.char + s.mention.entity.label
    )
    .join("");
}

export const MentionInput = forwardRef<HTMLTextAreaElement, MentionInputProps>(
  function MentionInput(
    {
      segments,
      onInput,
      onKeyDown,
      disabled = false,
      placeholder = "Ask a question...",
      className,
      onSubmit,
    },
    ref
  ) {
    const textareaRef = useRef<HTMLTextAreaElement>(null);
    // Track whether WE are updating the textarea (to avoid loops)
    const suppressRef = useRef(false);

    // Expose ref to parent (for popover anchoring)
    useEffect(() => {
      if (typeof ref === "function") {
        ref(textareaRef.current);
      } else if (ref) {
        (ref as React.MutableRefObject<HTMLTextAreaElement | null>).current =
          textareaRef.current;
      }
    }, [ref]);

    // Sync segments → textarea value (only when segments change externally,
    // e.g. after mention insertion or clear)
    useEffect(() => {
      if (!textareaRef.current || suppressRef.current) {
        suppressRef.current = false;
        return;
      }
      const text = segmentsToText(segments);
      if (textareaRef.current.value !== text) {
        textareaRef.current.value = text;
        // Place cursor at end
        textareaRef.current.selectionStart = text.length;
        textareaRef.current.selectionEnd = text.length;
        textareaRef.current.focus();
      }
    }, [segments]);

    const handleChange = useCallback(
      (e: React.ChangeEvent<HTMLTextAreaElement>) => {
        const text = e.target.value;
        const cursor = e.target.selectionStart ?? text.length;
        // Mark that we're driving this change so the sync effect doesn't fight us
        suppressRef.current = true;
        onInput(text, cursor);
      },
      [onInput]
    );

    const handleKeyDown = useCallback(
      (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
        // Delegate to parent handler (autocomplete navigation)
        onKeyDown(e);
        if (e.defaultPrevented) return;

        // Enter without shift = submit
        if (e.key === "Enter" && !e.shiftKey) {
          e.preventDefault();
          onSubmit?.();
        }
      },
      [onKeyDown, onSubmit]
    );

    // Auto-resize textarea to content
    const handleAutoResize = useCallback(() => {
      if (textareaRef.current) {
        textareaRef.current.style.height = "auto";
        textareaRef.current.style.height =
          Math.min(textareaRef.current.scrollHeight, 120) + "px";
      }
    }, []);

    // Focus on mount
    useEffect(() => {
      if (textareaRef.current && !disabled) {
        textareaRef.current.focus();
      }
    }, [disabled]);

    return (
      <textarea
        ref={textareaRef}
        rows={1}
        disabled={disabled}
        placeholder={placeholder}
        onChange={(e) => {
          handleChange(e);
          handleAutoResize();
        }}
        onKeyDown={handleKeyDown}
        className={cn(
          "placeholder:text-muted-foreground dark:bg-input/30 border-input min-h-[36px] w-full min-w-0 rounded-md border bg-transparent px-3 py-1.5 text-base shadow-xs transition-[color,box-shadow] outline-none resize-none md:text-sm",
          "focus-visible:border-ring focus-visible:ring-ring/50 focus-visible:ring-[3px]",
          disabled && "pointer-events-none cursor-not-allowed opacity-50",
          className
        )}
      />
    );
  }
);
