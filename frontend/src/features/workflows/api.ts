import { apiFetch, apiFetchWithMeta } from "@/lib/api/client";
import type { PageMeta } from "@/lib/api/types";

import type { WorkflowRun, WorkflowRunDetail } from "./types";

export function listWorkflowRuns(
  page: number,
  pageSize: number,
): Promise<{ data: WorkflowRun[]; meta: PageMeta | null }> {
  return apiFetchWithMeta<WorkflowRun[]>(
    `/api/v1/workflows/runs?page=${page}&page_size=${pageSize}`,
  );
}

export function getWorkflowRun(id: string): Promise<WorkflowRunDetail> {
  return apiFetch<WorkflowRunDetail>(`/api/v1/workflows/runs/${id}`);
}
