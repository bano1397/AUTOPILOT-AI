import { create } from "zustand";
import { createJSONStorage, persist } from "zustand/middleware";

import type { ChatTurn } from "@/features/agents/types";
import type { RagAskResult } from "@/features/rag/types";

/**
 * Conversation state shared across pages.
 *
 * Chat transcripts previously lived in component state, so navigating to
 * another page unmounted the component and silently wiped the conversation.
 * The store survives in-app navigation, and is persisted to sessionStorage
 * (per browser tab) so a page reload keeps the transcript too. Persistence is
 * skipped during SSR/hydration and triggered from Providers after mount, so
 * server and client render identically (no hydration mismatch).
 */
interface ChatState {
  agentTurns: ChatTurn[];
  conversationId?: string;
  assistantResult: RagAskResult | null;
  addAgentTurn: (turn: ChatTurn) => void;
  setAgentTurns: (turns: ChatTurn[]) => void;
  setConversationId: (id: string | undefined) => void;
  resetAgentChat: () => void;
  setAssistantResult: (result: RagAskResult | null) => void;
  clearAll: () => void;
}

export const useChatStore = create<ChatState>()(
  persist(
    (set) => ({
      agentTurns: [],
      conversationId: undefined,
      assistantResult: null,
      addAgentTurn: (turn) =>
        set((state) => ({ agentTurns: [...state.agentTurns, turn] })),
      setAgentTurns: (turns) => set({ agentTurns: turns }),
      setConversationId: (id) => set({ conversationId: id }),
      resetAgentChat: () => set({ agentTurns: [], conversationId: undefined }),
      setAssistantResult: (result) => set({ assistantResult: result }),
      clearAll: () =>
        set({
          agentTurns: [],
          conversationId: undefined,
          assistantResult: null,
        }),
    }),
    {
      name: "autopilot-chat",
      storage: createJSONStorage(() => sessionStorage),
      // Rehydrated explicitly after mount (see Providers).
      skipHydration: true,
    },
  ),
);
