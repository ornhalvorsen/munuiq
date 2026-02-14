"use client";

import {
  useRef,
  useCallback,
  useLayoutEffect,
  useEffect,
  useImperativeHandle,
  forwardRef,
} from "react";
import { cn } from "@/lib/utils";
import { MentionBadge } from "./mention-badge";
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
 * Get character offset of current selection within the contentEditable div.
 */
function getCharOffset(root: HTMLElement): number {
  const sel = window.getSelection();
  if (!sel || sel.rangeCount === 0) return -1;

  const range = sel.getRangeAt(0);
  const preRange = document.createRange();
  preRange.selectNodeContents(root);
  preRange.setEnd(range.startContainer, range.startOffset);
  return preRange.toString().length;
}

/**
 * Set cursor to a specific character offset within the contentEditable div.
 */
function setCharOffset(root: HTMLElement, offset: number): void {
  const sel = window.getSelection();
  if (!sel) return;

  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  let remaining = offset;
  let node: Text | null = null;

  while (walker.nextNode()) {
    const textNode = walker.currentNode as Text;
    if (remaining <= textNode.length) {
      node = textNode;
      break;
    }
    remaining -= textNode.length;
  }

  if (node) {
    const range = document.createRange();
    range.setStart(node, remaining);
    range.collapse(true);
    sel.removeAllRanges();
    sel.addRange(range);
  }
}

export const MentionInput = forwardRef<HTMLDivElement, MentionInputProps>(
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
    const divRef = useRef<HTMLDivElement>(null);
    const cursorRef = useRef<number>(-1);
    const isComposingRef = useRef(false);
    const suppressInputRef = useRef(false);

    useImperativeHandle(ref, () => divRef.current!);

    // Save cursor before React re-render
    const saveCursor = useCallback(() => {
      if (divRef.current) {
        cursorRef.current = getCharOffset(divRef.current);
      }
    }, []);

    // Restore cursor after render
    useLayoutEffect(() => {
      if (cursorRef.current >= 0 && divRef.current && !suppressInputRef.current) {
        requestAnimationFrame(() => {
          if (divRef.current && cursorRef.current >= 0) {
            setCharOffset(divRef.current, cursorRef.current);
          }
        });
      }
      suppressInputRef.current = false;
    }, [segments]);

    // Handle input events from contentEditable
    const handleInput = useCallback(() => {
      if (isComposingRef.current) return;
      if (!divRef.current) return;

      // Extract plain text and cursor offset from DOM
      const plainText = divRef.current.innerText || "";
      const offset = getCharOffset(divRef.current);

      // Save cursor for restore after React re-render
      cursorRef.current = offset;

      onInput(plainText, offset);
    }, [onInput]);

    // Handle paste — strip HTML
    const handlePaste = useCallback(
      (e: React.ClipboardEvent) => {
        e.preventDefault();
        const text = e.clipboardData.getData("text/plain");
        document.execCommand("insertText", false, text);
      },
      []
    );

    // Handle keydown — delegate to hook first
    const handleKeyDown = useCallback(
      (e: React.KeyboardEvent) => {
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

    // Render segments to DOM
    // We sync manually instead of using React children because contentEditable
    // and React don't play well together — React reconciliation can fight
    // with the browser's text editing.
    useEffect(() => {
      if (!divRef.current) return;

      saveCursor();

      const div = divRef.current;
      // Clear existing children
      div.innerHTML = "";

      for (let i = 0; i < segments.length; i++) {
        const seg = segments[i];
        if (seg.kind === "text") {
          const span = document.createElement("span");
          span.setAttribute("data-segment", "text");
          span.textContent = seg.text;
          div.appendChild(span);
        } else {
          // Mention badge — create inline non-editable span
          const badge = document.createElement("span");
          badge.setAttribute("data-segment", "mention");
          badge.setAttribute("data-mention-index", String(i));
          badge.contentEditable = "false";

          const colorMap: Record<string, string> = {
            blue: "bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400",
            amber:
              "bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-400",
          };
          const color =
            colorMap[seg.mention.trigger.color] ?? colorMap.blue;

          badge.className = `inline-flex items-center rounded px-1.5 py-0.5 text-xs font-medium ${color} mx-0.5 select-none`;
          badge.textContent = `${seg.mention.trigger.char}\u00A0${seg.mention.entity.label}`;
          div.appendChild(badge);
        }
      }

      // Restore cursor
      if (cursorRef.current >= 0) {
        requestAnimationFrame(() => {
          if (divRef.current) {
            setCharOffset(divRef.current, cursorRef.current);
          }
        });
      }
    }, [segments, saveCursor]);

    // Focus the input on mount
    useEffect(() => {
      if (divRef.current && !disabled) {
        divRef.current.focus();
      }
    }, [disabled]);

    return (
      <div className="relative flex-1">
        <div
          ref={divRef}
          contentEditable={!disabled}
          suppressContentEditableWarning
          onInput={handleInput}
          onPaste={handlePaste}
          onKeyDown={handleKeyDown}
          onCompositionStart={() => {
            isComposingRef.current = true;
          }}
          onCompositionEnd={() => {
            isComposingRef.current = false;
            handleInput();
          }}
          role="textbox"
          aria-placeholder={placeholder}
          aria-disabled={disabled}
          data-placeholder={placeholder}
          className={cn(
            "placeholder:text-muted-foreground dark:bg-input/30 border-input min-h-[36px] w-full min-w-0 rounded-md border bg-transparent px-3 py-1.5 text-base shadow-xs transition-[color,box-shadow] outline-none md:text-sm",
            "focus-visible:border-ring focus-visible:ring-ring/50 focus-visible:ring-[3px]",
            "empty:before:content-[attr(data-placeholder)] empty:before:text-muted-foreground empty:before:pointer-events-none",
            disabled && "pointer-events-none cursor-not-allowed opacity-50",
            className
          )}
        />
      </div>
    );
  }
);
