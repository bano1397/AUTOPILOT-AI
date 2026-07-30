export type WorkflowRunStatus =
  "running" | "awaiting_approval" | "completed" | "failed";

export interface WorkflowRun {
  id: string;
  workflow_name: string;
  /** The version that produced this run; null for pre-versioning runs. */
  workflow_version_id: string | null;
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

/** The executable description of a version's graph (backend: app/workflows/spec.py). */
export interface GraphSpec {
  topology: string;
  agents: string[];
  fallback_agent: string;
  approval_gate: boolean;
}

export interface WorkflowVersion {
  id: string;
  definition_id: string;
  version: number;
  graph_spec: GraphSpec;
  is_active: boolean;
  notes: string;
  created_at: string;
}

export interface WorkflowDefinition {
  id: string;
  name: string;
  description: string;
  cloned_from_id: string | null;
  created_at: string;
}

export interface WorkflowDefinitionDetail {
  definition: WorkflowDefinition;
  versions: WorkflowVersion[];
  active_version: WorkflowVersion | null;
}

/** A frame from the live-run WebSocket. */
export interface RunEvent {
  type:
    | "WorkflowStarted"
    | "WorkflowStepCompleted"
    | "WorkflowCompleted"
    | "WorkflowFailed"
    | "ping";
  occurred_at?: string | null;
  data?: Record<string, unknown>;
  /** Events the server discarded because this client fell behind. */
  dropped?: number;
}
