"use client";

import { type DragEvent, useState } from "react";

import { TaskCard } from "@/components/tasks/task-card";
import { STATUS_COLUMNS } from "@/components/tasks/task-shared";
import { Skeleton } from "@/components/ui/skeleton";
import { useTasks, useUpdateTask } from "@/features/tasks/hooks";
import type { TaskItem, TaskStatus } from "@/features/tasks/types";
import { cn } from "@/lib/utils";

export function TaskBoard() {
  // One wide page so every task lands on the board (grouped client-side).
  const { data, isLoading } = useTasks(1, undefined, 100);
  const update = useUpdateTask();

  const [draggingId, setDraggingId] = useState<string | null>(null);
  const [dragOver, setDragOver] = useState<TaskStatus | null>(null);
  // Optimistic status overrides so a dropped card moves instantly.
  const [override, setOverride] = useState<Record<string, TaskStatus>>({});

  const tasks: TaskItem[] = (data?.data ?? []).map((task) =>
    override[task.id] ? { ...task, status: override[task.id] } : task,
  );

  function drop(status: TaskStatus) {
    const id = draggingId;
    setDraggingId(null);
    setDragOver(null);
    if (!id) return;
    const current = tasks.find((task) => task.id === id);
    if (!current || current.status === status) return;
    setOverride((prev) => ({ ...prev, [id]: status }));
    update.mutate(
      { id, changes: { status } },
      {
        onSettled: () =>
          setOverride((prev) => {
            const next = { ...prev };
            delete next[id];
            return next;
          }),
      },
    );
  }

  if (isLoading) {
    return (
      <div className="grid gap-4 md:grid-cols-3">
        {STATUS_COLUMNS.map((column) => (
          <div key={column.key} className="space-y-3">
            <Skeleton className="h-6 w-24" />
            <Skeleton className="h-24 rounded-xl" />
            <Skeleton className="h-24 rounded-xl" />
          </div>
        ))}
      </div>
    );
  }

  return (
    <div className="grid gap-4 md:grid-cols-3">
      {STATUS_COLUMNS.map((column) => {
        const columnTasks = tasks.filter((task) => task.status === column.key);
        return (
          <div
            key={column.key}
            onDragOver={(event: DragEvent) => {
              event.preventDefault();
              setDragOver(column.key);
            }}
            onDragLeave={() =>
              setDragOver((s) => (s === column.key ? null : s))
            }
            onDrop={() => drop(column.key)}
            className={cn(
              "flex flex-col gap-3 rounded-2xl border bg-muted/30 p-3 transition-colors",
              dragOver === column.key && "border-primary bg-primary/5",
            )}
          >
            <div className="flex items-center gap-2 px-1">
              <span className={cn("size-2 rounded-full", column.accent)} />
              <span className="text-sm font-semibold">{column.label}</span>
              <span className="ml-auto rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground">
                {columnTasks.length}
              </span>
            </div>

            <div className="flex min-h-[6rem] flex-col gap-2.5">
              {columnTasks.length === 0 ? (
                <p className="rounded-lg border border-dashed py-6 text-center text-xs text-muted-foreground">
                  Drop tasks here
                </p>
              ) : (
                columnTasks.map((task) => (
                  <TaskCard
                    key={task.id}
                    task={task}
                    onDragStart={setDraggingId}
                    dragging={draggingId === task.id}
                  />
                ))
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
