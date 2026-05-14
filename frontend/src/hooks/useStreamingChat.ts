/**
 * Module 8 — useStreamingChat Hook
 * Core hook for streaming chat with the FastAPI backend.
 *
 * Handles:
 * - Sending queries in RAG or Agent mode
 * - Consuming SSE token stream and appending to message state
 * - Receiving citations after generation
 * - Showing agent intermediate steps
 * - Error handling and cleanup
 */
"use client";

import { useState, useCallback, useRef } from "react";

// ── Types ─────────────────────────────────────────────────────────────────────
export type MessageRole = "user" | "assistant";
export type ChatMode = "rag" | "agent";

export interface Citation {
  paper_id: string;
  title: string;
  authors: string[];
  relevance_score?: number;
}

export interface AgentStep {
  node: string;        // e.g. "orchestrator", "research", "critique"
  output: string;
  tool_call?: { tool: string; query: string };
}

export interface Message {
  id: string;
  role: MessageRole;
  content: string;
  citations: Citation[];
  agentSteps: AgentStep[];
  isStreaming: boolean;
  traceId?: string;
  error?: string;
}

// ── SSE Event types (must match FastAPI route) ────────────────────────────────
type SSEEvent =
  | { type: "token";      content: string }
  | { type: "citations";  data: Citation[] }
  | { type: "agent_step"; node: string; output: string; tool_call?: AgentStep["tool_call"] }
  | { type: "done";       trace_id: string }
  | { type: "error";      detail: string };

// ── Hook ──────────────────────────────────────────────────────────────────────
export function useStreamingChat(apiKey: string = "dev-key-local") {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [mode, setMode] = useState<ChatMode>("rag");
  const eventSourceRef = useRef<EventSource | null>(null);

  const sendMessage = useCallback(
    async (query: string) => {
      if (isStreaming) return;

      // Add user message
      const userMsg: Message = {
        id: crypto.randomUUID(),
        role: "user",
        content: query,
        citations: [],
        agentSteps: [],
        isStreaming: false,
      };

      // Add empty assistant message that will be filled by stream
      const assistantMsg: Message = {
        id: crypto.randomUUID(),
        role: "assistant",
        content: "",
        citations: [],
        agentSteps: [],
        isStreaming: true,
      };

      setMessages((prev) => [...prev, userMsg, assistantMsg]);
      setIsStreaming(true);

      // TODO: construct the SSE URL
      // const url = new URL(`${process.env.NEXT_PUBLIC_API_URL}/v1/chat`);
      // url.searchParams.set("query", query);
      // url.searchParams.set("mode", mode);
      //
      // Note: EventSource doesn't support custom headers.
      // Options:
      //   1. Pass API key as a query param (simpler, fine for local dev)
      //   2. Use fetch() with ReadableStream instead (more flexible, better for prod)
      //   See: https://developer.mozilla.org/en-US/docs/Web/API/Fetch_API/Using_Fetch#reading_a_response_body_as_a_stream

      // TODO: open EventSource and handle events
      // const es = new EventSource(url.toString());
      // eventSourceRef.current = es;
      //
      // es.onmessage = (event) => {
      //   const data: SSEEvent = JSON.parse(event.data);
      //
      //   if (data.type === "token") {
      //     setMessages((prev) => {
      //       const updated = [...prev];
      //       const last = { ...updated[updated.length - 1] };
      //       last.content += data.content;
      //       updated[updated.length - 1] = last;
      //       return updated;
      //     });
      //   }
      //
      //   if (data.type === "citations") { ... }
      //   if (data.type === "agent_step") { ... }
      //   if (data.type === "done") { es.close(); setIsStreaming(false); }
      //   if (data.type === "error") { ... }
      // };
      //
      // es.onerror = () => { es.close(); setIsStreaming(false); };

      throw new Error("TODO: implement sendMessage");
    },
    [isStreaming, mode, apiKey]
  );

  const stopStreaming = useCallback(() => {
    eventSourceRef.current?.close();
    setIsStreaming(false);
  }, []);

  const clearMessages = useCallback(() => {
    stopStreaming();
    setMessages([]);
  }, [stopStreaming]);

  return {
    messages,
    isStreaming,
    mode,
    setMode,
    sendMessage,
    stopStreaming,
    clearMessages,
  };
}
