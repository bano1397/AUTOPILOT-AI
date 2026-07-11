"use client";

import { Sparkles, Trash2 } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { PRIORITY_META } from "@/components/tasks/task-shared";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useDeleteTask, useTasks, useUpdateTask } from "@/features/tasks/hooks";
import type { TaskItem, TaskStatus } from "@/features/tasks/types";
import { cn, formatDate } from "@/lib/utils";

function TaskRow({ task }: { task: TaskItem }) {
  const update = useUpdateTask();
  const del = useDeleteTask();
  const priority = PRIORITY_META[task.priority];

  function confirmDelete() {
    toast(`Delete “${task.title}”?`, {
      action: {
        label: "Delete",
        onClick: () =>
          del.mutate(task.id, {
            onSuccess: () => toast.success("Task deleted"),
          }),
      },
    });
  }

  return (
    <TableRow className={cn(task.status === "done" && "opacity-60")}>
      <TableCell>
        <div className="font-medium">{task.title}</div>
        {task.description && (
          <div className="line-clamp-1 text-xs text-muted-foreground">
            {task.description}
          </div>
        )}
      </TableCell>
      <TableCell>
        <span
          className={cn(
            "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium",
            priority.badge,
          )}
        >
          <span className={cn("size-1.5 rounded-full", priority.dot)} />
          {priority.label}
        </span>
      </TableCell>
      <TableCell>
        <select
          value={task.status}
          disabled={update.isPending}
          onChange={(event) =>
            update.mutate({
              id: task.id,
              changes: { status: event.target.value as TaskStatus },
            })
          }
          className="h-8 rounded-md border border-input bg-background px-2 text-sm"
          aria-label={`Status of ${task.title}`}
        >
          <option value="todo">To do</option>
          <option value="in_progress">In progress</option>
          <option value="done">Done</option>
        </select>
      </TableCell>
      <TableCell>
        {task.source === "planner" ? (
          <span className="inline-flex items-center gap-1 text-xs font-medium text-violet-600 dark:text-violet-400">
            <Sparkles className="size-3" /> AI
          </span>
        ) : (
          <span className="text-xs text-muted-foreground">Manual</span>
        )}
      </TableCell>
      <TableCell className="text-sm text-muted-foreground">
        {formatDate(task.created_at)}
      </TableCell>
      <TableCell className="text-right">
        <button
          type="button"
          onClick={confirmDelete}
          aria-label={`Delete ${task.title}`}
          className="rounded-md p-1.5 text-muted-foreground transition-colors hover:text-rose-500"
        >
          <Trash2 className="size-4" />
        </button>
      </TableCell>
    </TableRow>
  );
}

export function TaskTable() {
  const [page, setPage] = useState(1);
  const { data, isLoading } = useTasks(page, undefined, 10);
  const items = data?.data ?? [];
  const meta = data?.meta;

  if (isLoading) {
    return <Skeleton className="h-64 w-full rounded-xl" />;
  }

  return (
    <div className="space-y-3">
      <div className="overflow-hidden rounded-xl border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Task</TableHead>
              <TableHead>Priority</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Source</TableHead>
              <TableHead>Created</TableHead>
              <TableHead className="w-12" />
            </TableRow>
          </TableHeader>
          <TableBody>
            {items.map((task) => (
              <TaskRow key={task.id} task={task} />
            ))}
          </TableBody>
        </Table>
      </div>

      {meta && meta.pages > 1 && (
        <div className="flex items-center justify-end gap-2 text-sm">
          <span className="text-muted-foreground">
            Page {meta.page} of {meta.pages}
          </span>
          <Button
            variant="outline"
            size="sm"
            disabled={page <= 1}
            onClick={() => setPage((c) => c - 1)}
          >
            Previous
          </Button>
          <Button
            variant="outline"
            size="sm"
            disabled={page >= meta.pages}
            onClick={() => setPage((c) => c + 1)}
          >
            Next
          </Button>
        </div>
      )}
    </div>
  );
}
