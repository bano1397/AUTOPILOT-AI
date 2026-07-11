import { apiFetch } from "@/lib/api/client";

import type { AgentAskResult } from "./types";

export interface AgentInfo {
  name: string;
  description: string;
}

export function listAgents(): Promise<AgentInfo[]> {
  return apiFetch<AgentInfo[]>("/api/v1/agents");
}

export function agentAsk(
  message: string,
  conversationId?: string,
  requireApproval = false,
): Promise<AgentAskResult> {
  return apiFetch<AgentAskResult>("/api/v1/agents/ask", {
    method: "POST",
    body: {
      message,
      require_approval: requireApproval,
      ...(conversationId ? { conversation_id: conversationId } : {}),
    },
  });
}
