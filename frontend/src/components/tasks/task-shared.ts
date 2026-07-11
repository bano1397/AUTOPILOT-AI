import type { TaskPriority, TaskStatus } from "@/features/tasks/types";

export const PRIORITY_META: Record<
  TaskPriority,
  { label: string; badge: string; dot: string }
> = {
  urgent: {
    label: "Urgent",
    badge: "bg-rose-500/10 text-rose-600 dark:text-rose-400",
    dot: "bg-rose-500",
  },
  high: {
    label: "High",
    badge: "bg-amber-500/10 text-amber-600 dark:text-amber-400",
    dot: "bg-amber-500",
  },
  medium: {
    label: "Medium",
    badge: "bg-indigo-500/10 text-indigo-600 dark:text-indigo-400",
    dot: "bg-indigo-500",
  },
  low: {
    label: "Low",
    badge: "bg-slate-500/10 text-slate-600 dark:text-slate-400",
    dot: "bg-slate-400",
  },
};

export const STATUS_COLUMNS: Array<{
  key: TaskStatus;
  label: string;
  accent: string;
}> = [
  { key: "todo", label: "To do", accent: "bg-slate-400" },
  { key: "in_progress", label: "In progress", accent: "bg-indigo-500" },
  { key: "done", label: "Done", accent: "bg-emerald-500" },
];
