"use client";

import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { ScrollArea } from "@/components/ui/scroll-area";
import type { AutocompleteState, MentionEntity } from "./types";

interface MentionPopoverProps {
  autocomplete: AutocompleteState;
  onSelect: (entity: MentionEntity) => void;
  onDismiss: () => void;
}

function boldMatch(text: string, query: string): React.ReactNode {
  if (!query) return text;
  const idx = text.toLowerCase().indexOf(query.toLowerCase());
  if (idx === -1) return text;
  return (
    <>
      {text.slice(0, idx)}
      <span className="font-semibold">{text.slice(idx, idx + query.length)}</span>
      {text.slice(idx + query.length)}
    </>
  );
}

export function MentionPopover({
  autocomplete,
  onSelect,
  onDismiss,
}: MentionPopoverProps) {
  const [pos, setPos] = useState<{ top: number; left: number } | null>(null);
  const popoverRef = useRef<HTMLDivElement>(null);
  const itemRefs = useRef<Map<number, HTMLElement>>(new Map());

  // Position the popover at the caret
  useEffect(() => {
    if (!autocomplete.active) {
      setPos(null);
      return;
    }

    const sel = window.getSelection();
    if (!sel || sel.rangeCount === 0) {
      setPos(null);
      return;
    }

    const range = sel.getRangeAt(0);
    const rect = range.getBoundingClientRect();

    // Position above caret by default, below if no space above
    const popoverHeight = 300; // max estimated height
    const spaceAbove = rect.top;
    const placeAbove = spaceAbove > popoverHeight;

    setPos({
      top: placeAbove ? rect.top - 4 : rect.bottom + 4,
      left: rect.left,
    });
  }, [autocomplete.active, autocomplete.query, autocomplete.results]);

  // Scroll highlighted item into view
  useEffect(() => {
    const el = itemRefs.current.get(autocomplete.highlightIndex);
    if (el) {
      el.scrollIntoView({ block: "nearest" });
    }
  }, [autocomplete.highlightIndex]);

  // Close on outside click
  useEffect(() => {
    if (!autocomplete.active) return;

    function handleClick(e: MouseEvent) {
      if (
        popoverRef.current &&
        !popoverRef.current.contains(e.target as Node)
      ) {
        onDismiss();
      }
    }

    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [autocomplete.active, onDismiss]);

  if (!autocomplete.active || !pos) return null;

  const isAbove = pos.top < 200; // rough heuristic

  const content = (
    <div
      ref={popoverRef}
      className="fixed z-50 w-72 rounded-md border bg-popover text-popover-foreground shadow-md animate-in fade-in-0 slide-in-from-bottom-2 duration-100"
      style={{
        top: isAbove ? pos.top : undefined,
        bottom: isAbove ? undefined : `${window.innerHeight - pos.top}px`,
        left: Math.min(pos.left, window.innerWidth - 300),
      }}
    >
      {/* Header */}
      <div className="flex items-center gap-1.5 border-b px-3 py-1.5 text-xs text-muted-foreground">
        <span className="font-mono font-semibold">
          {autocomplete.trigger?.char}
        </span>
        <span>{autocomplete.trigger?.label}s</span>
        {autocomplete.query && (
          <span className="ml-auto text-[10px] opacity-60">
            {autocomplete.results.length} results
          </span>
        )}
      </div>

      {/* Results */}
      {autocomplete.results.length === 0 ? (
        <div className="px-3 py-4 text-center text-xs text-muted-foreground">
          No matches for &ldquo;{autocomplete.query}&rdquo;
        </div>
      ) : (
        <ScrollArea className="max-h-[240px]">
          <div className="py-1">
            {autocomplete.results.map((entity, idx) => (
              <button
                key={entity.id}
                ref={(el) => {
                  if (el) itemRefs.current.set(idx, el);
                  else itemRefs.current.delete(idx);
                }}
                className={cn(
                  "w-full text-left px-3 py-1.5 text-sm cursor-pointer transition-colors",
                  idx === autocomplete.highlightIndex
                    ? "bg-accent text-accent-foreground"
                    : "hover:bg-accent/50"
                )}
                onMouseDown={(e) => {
                  e.preventDefault(); // Don't blur the input
                  onSelect(entity);
                }}
                onMouseEnter={() => {
                  // Could update highlight on hover if desired
                }}
              >
                <div className="font-medium">
                  {boldMatch(entity.label, autocomplete.query)}
                </div>
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
  );

  return createPortal(content, document.body);
}

function cn(...classes: (string | false | undefined)[]) {
  return classes.filter(Boolean).join(" ");
}
