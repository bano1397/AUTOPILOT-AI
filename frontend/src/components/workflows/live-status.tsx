"use client";

import { Activity } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { useLiveRunEvents } from "@/features/workflows/hooks";
import type { RunEvent } from "@/features/workflows/types";
import { cn } from "@/lib/utils";

const LABEL: Record<string, string> = {
  WorkflowStarted: "started",
  WorkflowStepCompleted: "step",
  WorkflowCompleted: "completed",
  WorkflowFailed: "failed",
};

const TONE: Record<string, string> = {
  WorkflowStarted: "bg-indigo-500",
  WorkflowStepCompleted: "bg-sky-500",
  WorkflowCompleted: "bg-emerald-500",
  WorkflowFailed: "bg-rose-500",
};

function describe(event: RunEvent): string {
  const data = event.data ?? {};
  const run = String(data.run_id ?? "").slice(0, 8);
  if (event.type === "WorkflowStepCompleted") {
    return `${run} · ${String(data.node_name ?? "node")} (${String(
      data.duration_ms ?? 0,
    )}ms)`;
  }
  if (event.type === "WorkflowFailed") {
    return `${run} · ${String(data.error ?? "failed")}`;
  }
  return `${run} · ${String(data.workflow_name ?? "run")}`;
}

/**
 * Live ticker of workflow activity, newest first.
 *
 * Shows only what arrived while this page was open — the socket carries no
 * history, and pretending otherwise by backfilling from the runs API would
 * blur "happening now" with "happened earlier".
 */
export function LiveStatus() {
  const { events, connected } = useLiveRunEvents();
  const recent = [...events].reverse().slice(0, 12);

  return (
    <div className="rounded-2xl border bg-card p-4">
      <div className="mb-3 flex items-center gap-2">
        <Activity className="size-4 text-primary" />
        <h3 className="text-sm font-medium">Live activity</h3>
        <Badge
          variant={connected ? "success" : "outline"}
          className="ml-auto text-[10px]"
        >
          {connected ? "connected" : "offline"}
        </Badge>
      </div>

      {recent.length === 0 ? (
        <p className="py-6 text-center text-xs text-muted-foreground">
          {connected
            ? "Waiting for activity — message the agents to see runs stream in."
            : "Not connected to the live stream."}
        </p>
      ) : (
        <ul className="space-y-1.5">
          {recent.map((event, index) => (
            <li
              key={`${event.occurred_at}-${index}`}
              className="flex items-center gap-2 text-xs"
            >
              <span
                className={cn(
                  "size-1.5 shrink-0 rounded-full",
                  TONE[event.type] ?? "bg-muted-foreground",
                )}
              />
              <span className="w-20 shrink-0 text-muted-foreground">
                {LABEL[event.type] ?? event.type}
              </span>
              <span className="truncate font-mono text-[11px]">
                {describe(event)}
              </span>
              {event.dropped ? (
                <Badge variant="warning" className="ml-auto text-[10px]">
                  {event.dropped} dropped
                </Badge>
              ) : null}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
