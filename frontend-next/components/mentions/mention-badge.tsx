"use client";

import type { Mention } from "./types";

const COLOR_MAP: Record<string, string> = {
  blue: "bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400",
  amber: "bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-400",
};

export function MentionBadge({ mention }: { mention: Mention }) {
  const colorClass = COLOR_MAP[mention.trigger.color] ?? COLOR_MAP.blue;

  return (
    <span
      className={`inline-flex items-center rounded px-1.5 py-0.5 text-xs font-medium ${colorClass} mx-0.5 select-none`}
      contentEditable={false}
    >
      {mention.trigger.char}
      {"\u00A0"}
      {mention.entity.label}
    </span>
  );
}
