"use client";

import { motion } from "framer-motion";
import { CalendarClock, GripVertical, Sparkles, Trash2 } from "lucide-react";
import { toast } from "sonner";

import { PRIORITY_META } from "@/components/tasks/task-shared";
import { useDeleteTask } from "@/features/tasks/hooks";
import type { TaskItem } from "@/features/tasks/types";
import { cn, formatDate } from "@/lib/utils";

export function TaskCard({
  task,
  onDragStart,
  dragging,
}: {
  task: TaskItem;
  onDragStart?: (id: string) => void;
  dragging?: boolean;
}) {
  const del = useDeleteTask();
  const priority = PRIORITY_META[task.priority];

  function confirmDelete() {
    toast(`Delete “${task.title}”?`, {
      action: {
        label: "Delete",
        onClick: () =>
          del.mutate(task.id, {
            onSuccess: () => toast.success("Task deleted"),
            onError: () => toast.error("Delete failed"),
          }),
      },
    });
  }

  return (
    <motion.div
      layout
      draggable={Boolean(onDragStart)}
      onDragStart={() => onDragStart?.(task.id)}
      className={cn(
        "group rounded-xl border bg-card p-3 shadow-sm transition-shadow hover:shadow-md",
        onDragStart && "cursor-grab active:cursor-grabbing",
        dragging && "opacity-50",
        task.status === "done" && "opacity-70",
      )}
    >
      <div className="flex items-start gap-2">
        {onDragStart && (
          <GripVertical className="mt-0.5 size-4 shrink-0 text-muted-foreground/40" />
        )}
        <div className="min-w-0 flex-1">
          <p
            className={cn(
              "text-sm font-medium",
              task.status === "done" && "line-through",
            )}
          >
            {task.title}
          </p>
          {task.description && (
            <p className="mt-0.5 line-clamp-2 text-xs text-muted-foreground">
              {task.description}
            </p>
          )}
        </div>
        <button
          type="button"
          onClick={confirmDelete}
          aria-label="Delete task"
          className="rounded-md p-1 text-muted-foreground opacity-0 transition-opacity hover:text-rose-500 group-hover:opacity-100"
        >
          <Trash2 className="size-3.5" />
        </button>
      </div>

      <div className="mt-2.5 flex flex-wrap items-center gap-2">
        <span
          className={cn(
            "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-medium",
            priority.badge,
          )}
        >
          <span className={cn("size-1.5 rounded-full", priority.dot)} />
          {priority.label}
        </span>
        {task.source === "planner" && (
          <span className="inline-flex items-center gap-1 rounded-full bg-violet-500/10 px-2 py-0.5 text-[11px] font-medium text-violet-600 dark:text-violet-400">
            <Sparkles className="size-3" />
            AI
          </span>
        )}
        {task.due_date && (
          <span className="inline-flex items-center gap-1 text-[11px] text-muted-foreground">
            <CalendarClock className="size-3" />
            {formatDate(task.due_date)}
          </span>
        )}
      </div>
    </motion.div>
  );
}
