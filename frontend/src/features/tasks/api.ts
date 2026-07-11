import { apiFetch, apiFetchWithMeta } from "@/lib/api/client";
import type { PageMeta } from "@/lib/api/types";

import type { TaskCreateInput, TaskItem, TaskStatus } from "./types";

export function listTasks(
  page: number,
  pageSize: number,
  status?: TaskStatus,
): Promise<{ data: TaskItem[]; meta: PageMeta | null }> {
  const filter = status ? `&status=${status}` : "";
  return apiFetchWithMeta<TaskItem[]>(
    `/api/v1/tasks?page=${page}&page_size=${pageSize}${filter}`,
  );
}

export function createTask(input: TaskCreateInput): Promise<TaskItem> {
  return apiFetch<TaskItem>("/api/v1/tasks", { method: "POST", body: input });
}

export function updateTask(
  id: string,
  changes: Partial<
    Pick<TaskItem, "title" | "description" | "priority" | "status">
  >,
): Promise<TaskItem> {
  return apiFetch<TaskItem>(`/api/v1/tasks/${id}`, {
    method: "PATCH",
    body: changes,
  });
}

export function deleteTask(id: string): Promise<unknown> {
  return apiFetch(`/api/v1/tasks/${id}`, { method: "DELETE" });
}
