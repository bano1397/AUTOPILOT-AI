"use client";

import { KanbanSquare, Table2 } from "lucide-react";
import { useState } from "react";

import { NewTaskDialog } from "@/components/tasks/new-task-dialog";
import { TaskBoard } from "@/components/tasks/task-board";
import { TaskTable } from "@/components/tasks/task-table";
import { STATUS_COLUMNS } from "@/components/tasks/task-shared";
import { useTasks } from "@/features/tasks/hooks";
import { cn } from "@/lib/utils";

export default function TasksPage() {
  const [view, setView] = useState<"board" | "table">("board");
  const all = useTasks(1, undefined, 100);
  const tasks = all.data?.data ?? [];

  const counts = {
    todo: tasks.filter((t) => t.status === "todo").length,
    in_progress: tasks.filter((t) => t.status === "in_progress").length,
    done: tasks.filter((t) => t.status === "done").length,
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Tasks</h1>
          <p className="text-muted-foreground">
            Plan and track work — drag cards across the board, or let the agents
            plan a goal for you.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-0.5 rounded-lg border bg-card p-0.5">
            <button
              type="button"
              onClick={() => setView("board")}
              className={cn(
                "flex items-center gap-1.5 rounded-md px-2.5 py-1 text-xs font-medium transition-colors",
                view === "board"
                  ? "bg-accent text-foreground"
                  : "text-muted-foreground hover:text-foreground",
              )}
            >
              <KanbanSquare className="size-4" /> Board
            </button>
            <button
              type="button"
              onClick={() => setView("table")}
              className={cn(
                "flex items-center gap-1.5 rounded-md px-2.5 py-1 text-xs font-medium transition-colors",
                view === "table"
                  ? "bg-accent text-foreground"
                  : "text-muted-foreground hover:text-foreground",
              )}
            >
              <Table2 className="size-4" /> Table
            </button>
          </div>
          <NewTaskDialog />
        </div>
      </div>

      {/* Status summary */}
      <div className="grid grid-cols-3 gap-3">
        {STATUS_COLUMNS.map((column) => (
          <div
            key={column.key}
            className="flex items-center gap-3 rounded-xl border bg-card p-4"
          >
            <span className={cn("size-2.5 rounded-full", column.accent)} />
            <div>
              <p className="text-xl font-semibold tabular-nums">
                {counts[column.key]}
              </p>
              <p className="text-xs text-muted-foreground">{column.label}</p>
            </div>
          </div>
        ))}
      </div>

      {view === "board" ? <TaskBoard /> : <TaskTable />}
    </div>
  );
}
