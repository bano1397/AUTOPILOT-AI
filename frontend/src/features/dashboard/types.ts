import type { AgentInfo } from "@/features/agents/api";
import type { AnalyticsOverview } from "@/features/analytics/types";
import type { Approval } from "@/features/approvals/types";
import type { WorkflowRun } from "@/features/workflows/types";

/** Everything the landing page renders, from one call. */
export interface DashboardData {
  analytics: AnalyticsOverview;
  pending_approvals: Approval[];
  pending_approval_count: number;
  agents: AgentInfo[];
  recent_runs: WorkflowRun[];
}
