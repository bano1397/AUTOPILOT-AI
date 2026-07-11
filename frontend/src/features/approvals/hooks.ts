import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { WORKFLOW_RUNS_KEY } from "@/features/workflows/hooks";

import { decideApproval, listPendingApprovals } from "./api";

const APPROVALS_KEY = ["approvals"];

export function usePendingApprovals(page: number, pageSize = 10) {
  return useQuery({
    queryKey: [...APPROVALS_KEY, page, pageSize],
    queryFn: () => listPendingApprovals(page, pageSize),
  });
}

/** Approve/reject a pending draft; refreshes approvals, runs, and threads. */
export function useDecideApproval() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      id,
      decision,
    }: {
      id: string;
      decision: "approved" | "rejected";
    }) => decideApproval(id, decision),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: APPROVALS_KEY });
      void queryClient.invalidateQueries({ queryKey: WORKFLOW_RUNS_KEY });
      void queryClient.invalidateQueries({ queryKey: ["conversations"] });
    },
  });
}
