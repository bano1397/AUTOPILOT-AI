import { apiFetch } from "@/lib/api/client";

import type { WorkspaceUser } from "./types";

/**
 * Fetch the workspace identity. There is no authentication (see
 * `docs/COMPLETION_PLAN.md` §3); the backend provisions this identity on first
 * use and every request runs as it.
 */
export function getWorkspaceUser(): Promise<WorkspaceUser> {
  return apiFetch<WorkspaceUser>("/api/v1/users/me");
}
