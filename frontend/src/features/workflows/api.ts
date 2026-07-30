import { apiFetch, apiFetchWithMeta } from "@/lib/api/client";
import type { PageMeta } from "@/lib/api/types";

import type {
  GraphSpec,
  WorkflowDefinition,
  WorkflowDefinitionDetail,
  WorkflowRun,
  WorkflowRunDetail,
  WorkflowVersion,
} from "./types";

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

// --- Definitions & versions (blueprint §20) ---------------------------------

export function listDefinitions(): Promise<{
  data: WorkflowDefinition[];
  meta: PageMeta | null;
}> {
  return apiFetchWithMeta<WorkflowDefinition[]>(
    "/api/v1/workflows/definitions?page_size=50",
  );
}

export function getDefinition(id: string): Promise<WorkflowDefinitionDetail> {
  return apiFetch<WorkflowDefinitionDetail>(
    `/api/v1/workflows/definitions/${id}`,
  );
}

export function listAgentCatalogue(): Promise<{ agents: string[] }> {
  return apiFetch<{ agents: string[] }>("/api/v1/workflows/agents-catalogue");
}

export function addVersion(
  definitionId: string,
  graphSpec: GraphSpec,
  notes: string,
  activate: boolean,
): Promise<WorkflowVersion> {
  return apiFetch<WorkflowVersion>(
    `/api/v1/workflows/definitions/${definitionId}/versions`,
    {
      method: "POST",
      body: { graph_spec: graphSpec, notes, activate },
    },
  );
}

export function activateVersion(versionId: string): Promise<WorkflowVersion> {
  return apiFetch<WorkflowVersion>(
    `/api/v1/workflows/versions/${versionId}/activate`,
    { method: "POST" },
  );
}

export function cloneDefinition(
  definitionId: string,
  name: string,
): Promise<WorkflowDefinitionDetail> {
  return apiFetch<WorkflowDefinitionDetail>(
    `/api/v1/workflows/definitions/${definitionId}/clone`,
    { method: "POST", body: { name } },
  );
}

export function listRunsForVersion(
  versionId: string,
): Promise<{ data: WorkflowRun[]; meta: PageMeta | null }> {
  return apiFetchWithMeta<WorkflowRun[]>(
    `/api/v1/workflows/versions/${versionId}/runs`,
  );
}
