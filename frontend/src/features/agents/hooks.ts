import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { CONVERSATIONS_KEY } from "@/features/conversations/hooks";
import { useChatStore } from "@/lib/chat/store";

import { agentAsk, listAgents } from "./api";

/** The registered agents available to the supervisor. */
export function useAgents() {
  return useQuery({ queryKey: ["agents", "list"], queryFn: listAgents });
}

/** Sends a message through the supervisor graph (on demand).
 *
 * The reply is appended to the shared chat store inside the mutation itself —
 * not in an ``onSuccess`` observer callback — so it still lands if the user
 * navigates away while the (slow, local-LLM) generation is in flight.
 */
export function useAgentAsk() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({
      message,
      conversationId,
      requireApproval,
    }: {
      message: string;
      conversationId?: string;
      requireApproval?: boolean;
    }) => {
      const result = await agentAsk(message, conversationId, requireApproval);
      const chat = useChatStore.getState();
      chat.setConversationId(result.conversation_id);
      chat.addAgentTurn({
        role: "assistant",
        content: result.answer,
        status: result.status,
        agent: result.agent,
        grounded: result.grounded,
        model: result.model,
        sources: result.sources,
        webSources: result.web_sources,
      });
      return result;
    },
    onSuccess: () => {
      // Surface the new/updated thread in the history rail.
      void queryClient.invalidateQueries({ queryKey: CONVERSATIONS_KEY });
    },
  });
}
