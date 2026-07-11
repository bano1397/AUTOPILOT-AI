import type { RagMatch } from "@/features/rag/types";

/** A web citation from the research agent. */
export interface WebSource {
  title: string;
  url: string;
  snippet: string;
}

export interface AgentAskResult {
  conversation_id: string;
  run_id: string;
  status: "completed" | "awaiting_approval";
  approval_id: string | null;
  message: string;
  answer: string;
  agent: string;
  grounded: boolean;
  model: string | null;
  sources: RagMatch[];
  web_sources: WebSource[];
}

/** A chat turn rendered in the agents page thread. */
export interface ChatTurn {
  role: "user" | "assistant";
  content: string;
  status?: "completed" | "awaiting_approval";
  agent?: string;
  grounded?: boolean;
  model?: string | null;
  sources?: RagMatch[];
  webSources?: WebSource[];
}
