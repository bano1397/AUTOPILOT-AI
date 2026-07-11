"use client";

import { CheckCircle2, CircleAlert, Clock, Loader2 } from "lucide-react";

import { Card, CardContent } from "@/components/ui/card";
import type { WorkflowRunStatus } from "@/features/workflows/types";
import { useWorkflowRuns } from "@/features/workflows/hooks";

function timeAgo(iso: string): string {
  const seconds = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000);
  if (seconds < 60) return "just now";
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

function StatusIcon({ status }: { status: WorkflowRunStatus }) {
  if (status === "completed")
    return <CheckCircle2 className="size-4 text-emerald-500" />;
  if (status === "failed")
    return <CircleAlert className="size-4 text-rose-500" />;
  if (status === "awaiting_approval")
    return <Clock className="size-4 text-amber-500" />;
  return <Loader2 className="size-4 animate-spin text-muted-foreground" />;
}

export function ActivityFeed() {
  const runs = useWorkflowRuns(1, 8);
  const items = runs.data?.data ?? [];

  return (
    <Card>
      <CardContent className="p-5">
        <h2 className="mb-4 text-base font-semibold">Recent activity</h2>
        {items.length === 0 ? (
          <p className="py-6 text-center text-sm text-muted-foreground">
            No activity yet.
          </p>
        ) : (
          <ol className="space-y-3">
            {items.map((run) => (
              <li key={run.id} className="flex items-start gap-3">
                <span className="mt-0.5">
                  <StatusIcon status={run.status} />
                </span>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm">
                    <span className="font-medium">{run.workflow_name}</span>{" "}
                    <span className="text-muted-foreground">
                      {run.status.replace("_", " ")}
                    </span>
                  </p>
                  <p className="text-xs text-muted-foreground">
                    {timeAgo(run.created_at)}
                  </p>
                </div>
              </li>
            ))}
          </ol>
        )}
      </CardContent>
    </Card>
  );
}
