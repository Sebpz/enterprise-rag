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
import { API_URL, API_KEY } from "../lib/api";

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
export function useStreamingChat(apiKey: string = API_KEY) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [mode, setMode] = useState<ChatMode>("rag");
  const eventSourceRef = useRef<EventSource | null>(null);

  const sendMessage = useCallback(
    async (query: string) => {
      if (isStreaming) return;

      const userMsg: Message = {
        id: crypto.randomUUID(),
        role: "user",
        content: query,
        citations: [],
        agentSteps: [],
        isStreaming: false,
      };

      const assistantId = crypto.randomUUID();
      const assistantMsg: Message = {
        id: assistantId,
        role: "assistant",
        content: "",
        citations: [],
        agentSteps: [],
        isStreaming: true,
      };

      setMessages((prev) => [...prev, userMsg, assistantMsg]);
      setIsStreaming(true);

      const url = new URL(`${API_URL}/v1/chat`);
      url.searchParams.set("query", query);
      url.searchParams.set("mode", mode);
      url.searchParams.set("stream", "true");
      url.searchParams.set("api_key", apiKey);

      const es = new EventSource(url.toString());
      eventSourceRef.current = es;

      const updateLast = (updater: (msg: Message) => Message) => {
        setMessages((prev) => {
          const updated = [...prev];
          const idx = updated.findLastIndex((m) => m.id === assistantId);
          if (idx === -1) return prev;
          updated[idx] = updater(updated[idx]);
          return updated;
        });
      };

      es.onmessage = (event) => {
        let data: SSEEvent;
        try {
          data = JSON.parse(event.data);
        } catch {
          return;
        }

        if (data.type === "token") {
          updateLast((msg) => ({ ...msg, content: msg.content + data.content }));
        } else if (data.type === "citations") {
          updateLast((msg) => ({ ...msg, citations: data.data }));
        } else if (data.type === "agent_step") {
          updateLast((msg) => ({
            ...msg,
            agentSteps: [
              ...msg.agentSteps,
              { node: data.node, output: data.output, tool_call: data.tool_call },
            ],
          }));
        } else if (data.type === "done") {
          updateLast((msg) => ({ ...msg, isStreaming: false, traceId: data.trace_id }));
          es.close();
          setIsStreaming(false);
        } else if (data.type === "error") {
          updateLast((msg) => ({ ...msg, isStreaming: false, error: data.detail }));
          es.close();
          setIsStreaming(false);
        }
      };

      es.onerror = () => {
        updateLast((msg) => ({
          ...msg,
          isStreaming: false,
          error: msg.content ? undefined : "Connection error",
        }));
        es.close();
        setIsStreaming(false);
      };
    },
    [isStreaming, mode, apiKey]
  );

  const stopStreaming = useCallback(() => {
    eventSourceRef.current?.close();
    setIsStreaming(false);
    setMessages((prev) => {
      const updated = [...prev];
      const last = updated[updated.length - 1];
      if (last?.isStreaming) {
        updated[updated.length - 1] = { ...last, isStreaming: false };
      }
      return updated;
    });
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
