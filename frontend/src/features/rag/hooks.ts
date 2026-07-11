import { useMutation } from "@tanstack/react-query";

import { useChatStore } from "@/lib/chat/store";

import { ragAsk, ragQuery } from "./api";

/** Runs a semantic search on demand (a mutation so nothing fires on mount). */
export function useRagQuery() {
  return useMutation({
    mutationFn: ({ query, topK }: { query: string; topK?: number }) =>
      ragQuery(query, topK),
  });
}

/** Asks a grounded question on demand.
 *
 * The answer is written to the shared chat store inside the mutation itself
 * so it survives navigating away while the generation is in flight.
 */
export function useRagAsk() {
  return useMutation({
    mutationFn: async ({ query, topK }: { query: string; topK?: number }) => {
      const result = await ragAsk(query, topK);
      useChatStore.getState().setAssistantResult(result);
      return result;
    },
  });
}
