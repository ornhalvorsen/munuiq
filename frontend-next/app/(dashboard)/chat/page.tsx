"use client";

import { ChatInterface } from "@/components/analytics/chat-interface";

export default function ChatPage() {
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">AI Chat</h1>
      <ChatInterface />
    </div>
  );
}
