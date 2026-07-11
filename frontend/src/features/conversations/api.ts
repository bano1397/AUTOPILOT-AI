import { apiFetch, apiFetchWithMeta } from "@/lib/api/client";
import type { PageMeta } from "@/lib/api/types";

import type { Conversation, ConversationDetail } from "./types";

export function listConversations(
  page: number,
  pageSize = 20,
): Promise<{ data: Conversation[]; meta: PageMeta | null }> {
  return apiFetchWithMeta<Conversation[]>(
    `/api/v1/conversations?page=${page}&page_size=${pageSize}`,
  );
}

export function getConversation(id: string): Promise<ConversationDetail> {
  return apiFetch<ConversationDetail>(`/api/v1/conversations/${id}`);
}
