import { useQuery } from "@tanstack/react-query";

import { getConversation, listConversations } from "./api";

export const CONVERSATIONS_KEY = ["conversations"];

/** Paginated list of the current user's conversations (most recent first). */
export function useConversations(page = 1) {
  return useQuery({
    queryKey: [...CONVERSATIONS_KEY, page],
    queryFn: () => listConversations(page),
  });
}

/** Full message history for one conversation; only fetched when `id` is set. */
export function useConversation(id: string | null) {
  return useQuery({
    queryKey: [...CONVERSATIONS_KEY, "detail", id],
    queryFn: () => getConversation(id as string),
    enabled: Boolean(id),
  });
}
