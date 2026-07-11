import type { RagMatch } from "@/features/rag/types";

export type ApprovalStatus = "pending" | "approved" | "rejected";

export interface ApprovalPayload {
  message?: string;
  conversation_id?: string;
  draft_answer?: string;
  agent?: string;
  grounded?: boolean;
  model?: string | null;
  sources?: RagMatch[];
}

export interface Approval {
  id: string;
  run_id: string;
  action_type: string;
  status: ApprovalStatus;
  payload: ApprovalPayload | null;
  created_at: string;
  decided_at: string | null;
}

export interface ApprovalDecisionResult {
  approval: Approval;
  answer: string;
  agent: string;
  grounded: boolean;
  model: string | null;
  sources: RagMatch[];
}
