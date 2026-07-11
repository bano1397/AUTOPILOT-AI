"use client";

import { motion } from "framer-motion";
import { Activity, Bot, Clock, FileCheck2, Gauge } from "lucide-react";

import { cn } from "@/lib/utils";

type Health = "operational" | "connecting" | "unreachable";

const STATUS: Record<Health, { label: string; dot: string; text: string }> = {
  operational: {
    label: "All AI systems operational",
    dot: "bg-emerald-500",
    text: "text-emerald-600 dark:text-emerald-400",
  },
  connecting: {
    label: "Connecting to services…",
    dot: "bg-amber-500",
    text: "text-amber-600 dark:text-amber-400",
  },
  unreachable: {
    label: "Some services are unreachable",
    dot: "bg-rose-500",
    text: "text-rose-600 dark:text-rose-400",
  },
};

function Metric({
  icon: Icon,
  label,
  value,
}: {
  icon: typeof Bot;
  label: string;
  value: string;
}) {
  return (
    <div className="flex items-center gap-2">
      <Icon className="size-4 text-muted-foreground" />
      <span className="text-sm font-medium tabular-nums">{value}</span>
      <span className="text-xs text-muted-foreground">{label}</span>
    </div>
  );
}

export function StatusBanner({
  health,
  agents,
  runs,
  avgLatency,
  approvals,
}: {
  health: Health;
  agents: string;
  runs: string;
  avgLatency: string;
  approvals: string;
}) {
  const status = STATUS[health];
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, delay: 0.05 }}
      className="relative overflow-hidden rounded-xl border bg-gradient-to-br from-indigo-500/10 via-violet-500/5 to-transparent p-5"
    >
      <div className="flex flex-wrap items-center gap-x-6 gap-y-3">
        <div className="flex items-center gap-2.5">
          <span className="relative flex size-2.5">
            <span
              className={cn(
                "absolute inline-flex h-full w-full animate-ping rounded-full opacity-75",
                status.dot,
              )}
            />
            <span
              className={cn(
                "relative inline-flex size-2.5 rounded-full",
                status.dot,
              )}
            />
          </span>
          <span className={cn("text-sm font-semibold", status.text)}>
            {status.label}
          </span>
        </div>
        <div className="flex flex-wrap items-center gap-x-5 gap-y-2">
          <Metric icon={Bot} value={agents} label="agents" />
          <Metric icon={Activity} value={runs} label="runs · 30d" />
          <Metric icon={Gauge} value={avgLatency} label="avg latency" />
          <Metric icon={FileCheck2} value={approvals} label="pending" />
          <Metric icon={Clock} value="Live" label="monitoring" />
        </div>
      </div>
    </motion.div>
  );
}
