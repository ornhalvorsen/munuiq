"use client";

import { ChatInterfaceV2 } from "@/components/analytics/chat-interface-v2";

export default function ChatV2Page() {
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">AI Chat v2</h1>
      <ChatInterfaceV2 />
    </div>
  );
}
