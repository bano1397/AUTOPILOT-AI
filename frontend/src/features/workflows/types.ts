export type WorkflowRunStatus =
  "running" | "awaiting_approval" | "completed" | "failed";

export interface WorkflowRun {
  id: string;
  workflow_name: string;
  status: WorkflowRunStatus;
  error: string | null;
  created_at: string;
  ended_at: string | null;
  duration_ms: number | null;
}

export interface WorkflowStep {
  id: string;
  position: number;
  node_name: string;
  duration_ms: number;
}

export interface WorkflowRunDetail {
  run: WorkflowRun;
  input: Record<string, unknown> | null;
  output: Record<string, unknown> | null;
  steps: WorkflowStep[];
}
