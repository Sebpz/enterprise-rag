"use client";

import { useEffect, useRef } from "react";
import type { Message } from "../../hooks/useStreamingChat";
import { CitationChip } from "./CitationChip";
import { AgentSteps } from "./AgentSteps";
import { submitFeedback } from "../../lib/api";

interface MessageListProps {
  messages: Message[];
}

export function MessageList({ messages }: MessageListProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  if (messages.length === 0) {
    return (
      <div className="flex-1 flex items-center justify-center text-slate-500 text-sm">
        Ask a question about ArXiv ML research
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto px-4 py-6 space-y-6">
      {messages.map((msg) => (
        <div
          key={msg.id}
          className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
        >
          <div
            className={`max-w-2xl w-full ${
              msg.role === "user"
                ? "bg-sky-900/40 border border-sky-800 ml-16"
                : "bg-slate-800 border border-slate-700 mr-16"
            } rounded-xl px-4 py-3`}
          >
            {msg.role === "assistant" && msg.agentSteps.length > 0 && (
              <AgentSteps steps={msg.agentSteps} />
            )}

            <p className="text-slate-100 text-sm whitespace-pre-wrap leading-relaxed">
              {msg.content}
              {msg.isStreaming && (
                <span className="inline-block w-1.5 h-4 bg-sky-400 ml-0.5 animate-pulse align-middle" />
              )}
            </p>

            {msg.error && (
              <p className="mt-2 text-red-400 text-xs">Error: {msg.error}</p>
            )}

            {msg.citations.length > 0 && (
              <div className="mt-3 flex flex-wrap gap-1.5">
                {msg.citations.map((c, i) => (
                  <CitationChip key={c.paper_id} citation={c} index={i + 1} />
                ))}
              </div>
            )}

            {msg.role === "assistant" && !msg.isStreaming && msg.traceId && (
              <div className="mt-3 flex gap-2">
                <button
                  onClick={() => submitFeedback(msg.traceId!, 1)}
                  className="text-xs text-slate-400 hover:text-green-400 transition-colors"
                  title="Helpful"
                >
                  👍
                </button>
                <button
                  onClick={() => submitFeedback(msg.traceId!, -1)}
                  className="text-xs text-slate-400 hover:text-red-400 transition-colors"
                  title="Not helpful"
                >
                  👎
                </button>
              </div>
            )}
          </div>
        </div>
      ))}
      <div ref={bottomRef} />
    </div>
  );
}
