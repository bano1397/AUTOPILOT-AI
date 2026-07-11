import { apiFetch, apiFetchWithMeta } from "@/lib/api/client";
import type { PageMeta } from "@/lib/api/types";

import type { Approval, ApprovalDecisionResult } from "./types";

export function listPendingApprovals(
  page: number,
  pageSize: number,
): Promise<{ data: Approval[]; meta: PageMeta | null }> {
  return apiFetchWithMeta<Approval[]>(
    `/api/v1/approvals?page=${page}&page_size=${pageSize}`,
  );
}

export function decideApproval(
  id: string,
  decision: "approved" | "rejected",
): Promise<ApprovalDecisionResult> {
  return apiFetch<ApprovalDecisionResult>(`/api/v1/approvals/${id}/decision`, {
    method: "POST",
    body: { decision },
  });
}
