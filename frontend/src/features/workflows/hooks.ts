import { useQuery } from "@tanstack/react-query";

import { getWorkflowRun, listWorkflowRuns } from "./api";

export const WORKFLOW_RUNS_KEY = ["workflow-runs"];

export function useWorkflowRuns(page: number, pageSize = 10) {
  return useQuery({
    queryKey: [...WORKFLOW_RUNS_KEY, page, pageSize],
    queryFn: () => listWorkflowRuns(page, pageSize),
  });
}

/** Run detail (steps + payloads); fetched lazily when a row is expanded. */
export function useWorkflowRun(id: string | null) {
  return useQuery({
    queryKey: [...WORKFLOW_RUNS_KEY, "detail", id],
    queryFn: () => getWorkflowRun(id as string),
    enabled: id !== null,
  });
}
