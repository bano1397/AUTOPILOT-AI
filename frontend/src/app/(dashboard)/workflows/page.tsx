"use client";

import { Loader2, Workflow as WorkflowIcon } from "lucide-react";
import { useEffect, useState } from "react";

import { WorkflowGraph } from "@/components/workflows/workflow-graph";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useWorkflowRun, useWorkflowRuns } from "@/features/workflows/hooks";
import type {
  WorkflowRun,
  WorkflowRunStatus,
} from "@/features/workflows/types";
import { cn, formatDate, formatDuration } from "@/lib/utils";

const STATUS_META: Record<
  WorkflowRunStatus,
  {
    label: string;
    badge: "success" | "warning" | "destructive" | "secondary";
    accent: string;
  }
> = {
  completed: { label: "Completed", badge: "success", accent: "bg-emerald-500" },
  awaiting_approval: {
    label: "Awaiting approval",
    badge: "warning",
    accent: "bg-amber-500",
  },
  failed: { label: "Failed", badge: "destructive", accent: "bg-rose-500" },
  running: { label: "Running", badge: "secondary", accent: "bg-indigo-500" },
};

export default function WorkflowsPage() {
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<string | null>(null);
  const runs = useWorkflowRuns(page);

  const items = runs.data?.data ?? [];
  const meta = runs.data?.meta;
  const firstId = items[0]?.id;

  // Default-select the first run once loaded.
  useEffect(() => {
    if (!selected && firstId) setSelected(firstId);
  }, [firstId, selected]);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="flex items-center gap-2 text-2xl font-semibold tracking-tight">
            <WorkflowIcon className="size-6 text-primary" />
            Workflows
          </h1>
          <p className="text-muted-foreground">
            Every agent execution as a step-by-step graph — timing, and outcome.
          </p>
        </div>
        {meta && (
          <Badge variant="outline" className="text-sm">
            {meta.total} run{meta.total === 1 ? "" : "s"}
          </Badge>
        )}
      </div>

      {runs.isPending ? (
        <div className="grid gap-4 lg:grid-cols-[20rem_1fr]">
          <Skeleton className="h-96 rounded-xl" />
          <Skeleton className="h-96 rounded-xl" />
        </div>
      ) : items.length === 0 ? (
        <div className="flex flex-col items-center gap-2 rounded-2xl border py-20 text-center text-muted-foreground">
          <WorkflowIcon className="size-8" />
          <p className="text-sm">
            No workflow runs yet — send a message to the agents to create one.
          </p>
        </div>
      ) : (
        <div className="grid gap-4 lg:grid-cols-[20rem_1fr]">
          {/* Run list */}
          <div className="space-y-2">
            {items.map((run) => (
              <RunListItem
                key={run.id}
                run={run}
                active={run.id === selected}
                onSelect={() => setSelected(run.id)}
              />
            ))}
            {meta && meta.pages > 1 && (
              <div className="flex items-center justify-between pt-1 text-xs text-muted-foreground">
                <span>
                  Page {meta.page}/{meta.pages}
                </span>
                <div className="flex gap-1">
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={page <= 1}
                    onClick={() => setPage((c) => c - 1)}
                  >
                    Prev
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
              </div>
            )}
          </div>

          {/* Detail */}
          <div className="rounded-2xl border bg-card p-5">
            {selected ? (
              <RunDetail runId={selected} />
            ) : (
              <p className="py-16 text-center text-sm text-muted-foreground">
                Select a run to see its execution graph.
              </p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function RunListItem({
  run,
  active,
  onSelect,
}: {
  run: WorkflowRun;
  active: boolean;
  onSelect: () => void;
}) {
  const status = STATUS_META[run.status];
  return (
    <button
      type="button"
      onClick={onSelect}
      className={cn(
        "flex w-full flex-col gap-1.5 rounded-xl border p-3 text-left transition-colors",
        active ? "border-primary/40 bg-primary/5" : "hover:bg-accent",
      )}
    >
      <div className="flex items-center gap-2">
        <span className={cn("size-2 shrink-0 rounded-full", status.accent)} />
        <span className="truncate text-sm font-medium">
          {run.workflow_name}
        </span>
      </div>
      <div className="flex items-center justify-between">
        <Badge variant={status.badge}>{status.label}</Badge>
        <span className="text-xs text-muted-foreground">
          {run.duration_ms !== null ? formatDuration(run.duration_ms) : "—"}
        </span>
      </div>
      <span className="text-[11px] text-muted-foreground">
        {formatDate(run.created_at)}
      </span>
    </button>
  );
}

function RunDetail({ runId }: { runId: string }) {
  const detail = useWorkflowRun(runId);

  if (detail.isPending) {
    return (
      <div className="flex items-center gap-2 py-16 text-sm text-muted-foreground">
        <Loader2 className="size-4 animate-spin" /> Loading run…
      </div>
    );
  }
  if (detail.isError || !detail.data) {
    return (
      <p className="py-16 text-center text-sm text-destructive">
        Unable to load run detail.
      </p>
    );
  }

  const { run, steps, output } = detail.data;
  const status = STATUS_META[run.status];

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center gap-2">
        <h2 className="text-lg font-semibold">{run.workflow_name}</h2>
        <Badge variant={status.badge}>{status.label}</Badge>
        <span className="ml-auto text-sm text-muted-foreground">
          {run.duration_ms !== null ? formatDuration(run.duration_ms) : "—"} ·{" "}
          {steps.length} step{steps.length === 1 ? "" : "s"}
        </span>
      </div>

      {run.error && (
        <p className="rounded-lg border border-rose-500/30 bg-rose-500/5 p-3 text-sm text-rose-600 dark:text-rose-400">
          {run.error}
        </p>
      )}

      <div>
        <p className="mb-3 text-xs font-medium uppercase tracking-wide text-muted-foreground">
          Execution graph
        </p>
        <WorkflowGraph steps={steps} accent={status.accent} />
      </div>

      {output && (
        <div>
          <p className="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
            Output
          </p>
          <pre className="scrollbar-thin overflow-x-auto rounded-lg border bg-muted/50 p-3 text-xs">
            {JSON.stringify(output, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
}
