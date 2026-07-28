import { apiFetch } from "@/lib/api/client";

import type { ToolInfo, ToolInvokeResult } from "./types";

export function listTools(category?: string): Promise<ToolInfo[]> {
  const query = category ? `?category=${encodeURIComponent(category)}` : "";
  return apiFetch<ToolInfo[]>(`/api/v1/tools${query}`);
}

export function listToolCategories(): Promise<string[]> {
  return apiFetch<string[]>("/api/v1/tools/categories");
}

export function invokeTool(
  name: string,
  args: Record<string, unknown>,
): Promise<ToolInvokeResult> {
  return apiFetch<ToolInvokeResult>(
    `/api/v1/tools/${encodeURIComponent(name)}/invoke`,
    { method: "POST", body: { args } },
  );
}
