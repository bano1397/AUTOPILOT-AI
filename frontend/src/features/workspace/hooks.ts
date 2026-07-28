import { useQuery } from "@tanstack/react-query";

import { getWorkspaceUser } from "./api";

/**
 * The workspace identity, cached by TanStack Query. This replaces the former
 * auth store: with no tokens to hold there is no client-side session state, so
 * the query cache is the only place the identity needs to live.
 */
export function useWorkspaceUser() {
  return useQuery({
    queryKey: ["workspace-user"],
    queryFn: getWorkspaceUser,
    staleTime: Infinity,
  });
}
