"use client";

import { motion } from "framer-motion";
import { ArrowRight, Flag, PlayCircle } from "lucide-react";

import type { WorkflowStep } from "@/features/workflows/types";
import { cn, formatDuration } from "@/lib/utils";

/**
 * Renders a run's recorded steps as a left-to-right execution graph:
 * Start → node → node → … → End. Purely a visualization of real step data
 * (node_name + duration); nodes are not editable.
 */
export function WorkflowGraph({
  steps,
  accent,
}: {
  steps: WorkflowStep[];
  accent: string;
}) {
  if (steps.length === 0) {
    return (
      <p className="rounded-lg border border-dashed py-8 text-center text-sm text-muted-foreground">
        No steps were recorded for this run.
      </p>
    );
  }

  const ordered = [...steps].sort((a, b) => a.position - b.position);

  return (
    <div className="flex flex-wrap items-stretch gap-y-3">
      <Terminal icon={PlayCircle} label="Start" />
      <Connector index={0} />
      {ordered.map((step, index) => (
        <div key={step.id} className="flex items-stretch">
          <motion.div
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.25, delay: index * 0.08 }}
            className="flex min-w-[8rem] flex-col rounded-xl border bg-card p-3 shadow-sm"
          >
            <div className="flex items-center gap-2">
              <span
                className={cn(
                  "flex size-5 items-center justify-center rounded-full text-[10px] font-semibold text-white",
                  accent,
                )}
              >
                {index + 1}
              </span>
              <code className="truncate text-xs font-medium">
                {step.node_name}
              </code>
            </div>
            <span className="mt-1.5 text-[11px] text-muted-foreground">
              {formatDuration(step.duration_ms)}
            </span>
          </motion.div>
          <Connector index={index + 1} />
        </div>
      ))}
      <Terminal icon={Flag} label="End" />
    </div>
  );
}

function Connector({ index }: { index: number }) {
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ delay: index * 0.08 + 0.1 }}
      className="flex items-center px-1 text-muted-foreground/50"
    >
      <ArrowRight className="size-4" />
    </motion.div>
  );
}

function Terminal({ icon: Icon, label }: { icon: typeof Flag; label: string }) {
  return (
    <div className="flex flex-col items-center justify-center rounded-xl border bg-muted/40 px-3 py-2">
      <Icon className="size-4 text-muted-foreground" />
      <span className="mt-1 text-[11px] font-medium text-muted-foreground">
        {label}
      </span>
    </div>
  );
}
