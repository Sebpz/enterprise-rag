"use client";

import { create } from "zustand";

type ChatMode = "rag" | "agent";

interface ChatStore {
  mode: ChatMode;
  setMode: (mode: ChatMode) => void;
  apiKey: string;
}

export const useChatStore = create<ChatStore>((set) => ({
  mode: "rag",
  setMode: (mode) => set({ mode }),
  apiKey: "dev-key-local",
}));
