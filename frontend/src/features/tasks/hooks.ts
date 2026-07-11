import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { createTask, deleteTask, listTasks, updateTask } from "./api";
import type { TaskCreateInput, TaskItem, TaskStatus } from "./types";

const TASKS_KEY = ["tasks"];

export function useTasks(page: number, status?: TaskStatus, pageSize = 10) {
  return useQuery({
    queryKey: [...TASKS_KEY, page, pageSize, status ?? "all"],
    queryFn: () => listTasks(page, pageSize, status),
  });
}

export function useCreateTask() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: TaskCreateInput) => createTask(input),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: TASKS_KEY }),
  });
}

export function useUpdateTask() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      id,
      changes,
    }: {
      id: string;
      changes: Partial<
        Pick<TaskItem, "title" | "description" | "priority" | "status">
      >;
    }) => updateTask(id, changes),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: TASKS_KEY }),
  });
}

export function useDeleteTask() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => deleteTask(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: TASKS_KEY }),
  });
}
