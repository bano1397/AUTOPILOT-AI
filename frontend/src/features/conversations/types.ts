import type { RagMatch } from "@/features/rag/types";
import type { WebSource } from "@/features/agents/types";

export interface Conversation {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
}

/** Metadata stored alongside an assistant message (agent, model, citations). */
export interface MessageMeta {
  agent?: string;
  model?: string | null;
  grounded?: boolean;
  sources?: RagMatch[];
  web_sources?: WebSource[];
}

export interface Message {
  id: string;
  position: number;
  role: "user" | "assistant";
  content: string;
  meta: MessageMeta | null;
  created_at: string;
}

export interface ConversationDetail {
  conversation: Conversation;
  messages: Message[];
}
