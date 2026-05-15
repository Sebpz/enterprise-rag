"use client";

import { useState, useRef, KeyboardEvent } from "react";
import { useStreamingChat } from "../../hooks/useStreamingChat";
import { MessageList } from "../../components/chat/MessageList";

export default function ChatPage() {
  const [input, setInput] = useState("");
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const { messages, isStreaming, mode, setMode, sendMessage, stopStreaming, clearMessages } =
    useStreamingChat();

  const handleSend = () => {
    const q = input.trim();
    if (!q || isStreaming) return;
    setInput("");
    sendMessage(q);
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-slate-800 bg-slate-900">
        <span className="text-sm font-semibold text-white">ArXiv Research Assistant</span>
        <div className="flex items-center gap-3">
          {/* Mode toggle */}
          <div className="flex rounded-lg overflow-hidden border border-slate-700 text-xs">
            {(["rag", "agent"] as const).map((m) => (
              <button
                key={m}
                onClick={() => setMode(m)}
                className={`px-3 py-1.5 uppercase tracking-wide transition-colors ${
                  mode === m
                    ? "bg-sky-700 text-white"
                    : "bg-slate-800 text-slate-400 hover:text-white"
                }`}
              >
                {m}
              </button>
            ))}
          </div>
          <button
            onClick={clearMessages}
            className="text-xs text-slate-400 hover:text-white transition-colors"
          >
            Clear
          </button>
        </div>
      </div>

      {/* Messages */}
      <MessageList messages={messages} />

      {/* Input */}
      <div className="border-t border-slate-800 bg-slate-900 px-4 py-3">
        <div className="flex gap-2 items-end max-w-3xl mx-auto">
          <textarea
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask about ML papers… (Enter to send, Shift+Enter for newline)"
            rows={1}
            className="flex-1 resize-none rounded-xl bg-slate-800 border border-slate-700 text-slate-100 text-sm px-4 py-2.5 placeholder-slate-500 focus:outline-none focus:border-sky-600 focus:ring-1 focus:ring-sky-600 min-h-[44px] max-h-32 overflow-y-auto"
            style={{ height: "auto" }}
            onInput={(e) => {
              const t = e.currentTarget;
              t.style.height = "auto";
              t.style.height = Math.min(t.scrollHeight, 128) + "px";
            }}
          />
          {isStreaming ? (
            <button
              onClick={stopStreaming}
              className="px-4 py-2.5 rounded-xl bg-red-700 hover:bg-red-600 text-white text-sm font-medium transition-colors flex-shrink-0"
            >
              Stop
            </button>
          ) : (
            <button
              onClick={handleSend}
              disabled={!input.trim()}
              className="px-4 py-2.5 rounded-xl bg-sky-700 hover:bg-sky-600 disabled:opacity-40 disabled:cursor-not-allowed text-white text-sm font-medium transition-colors flex-shrink-0"
            >
              Send
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
