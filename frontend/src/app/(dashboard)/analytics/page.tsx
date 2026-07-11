"use client";

import {
  Activity,
  BarChart3,
  Cpu,
  DollarSign,
  Gauge,
  type LucideIcon,
  TriangleAlert,
} from "lucide-react";
import { useState } from "react";

import { FeatureBarChart } from "@/components/analytics/feature-bar-chart";
import { StatusDonut } from "@/components/analytics/status-donut";
import {
  UsageAreaChart,
  type UsageMetric,
} from "@/components/analytics/usage-area-chart";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useAnalyticsOverview } from "@/features/analytics/hooks";
import type { AnalyticsTotals } from "@/features/analytics/types";
import { cn, formatDuration } from "@/lib/utils";

const RANGES = [7, 30, 90];
const METRICS: { key: UsageMetric; label: string }[] = [
  { key: "executions", label: "Executions" },
  { key: "total_tokens", label: "Tokens" },
  { key: "cost_usd", label: "Cost" },
];

function StatTile({
  icon: Icon,
  label,
  value,
  hint,
  tint,
}: {
  icon: LucideIcon;
  label: string;
  value: string;
  hint?: string;
  tint: string;
}) {
  return (
    <Card>
      <CardContent className="flex items-start justify-between p-4">
        <div className="space-y-1">
          <p className="text-xs text-muted-foreground">{label}</p>
          <p className="text-2xl font-semibold tabular-nums tracking-tight">
            {value}
          </p>
          {hint && <p className="text-[11px] text-muted-foreground">{hint}</p>}
        </div>
        <div
          className={cn(
            "flex size-9 items-center justify-center rounded-xl",
            tint,
          )}
        >
          <Icon className="size-5" />
        </div>
      </CardContent>
    </Card>
  );
}

function tiles(totals: AnalyticsTotals) {
  return [
    {
      icon: Activity,
      label: "Executions",
      value: totals.executions.toLocaleString(),
      tint: "bg-indigo-500/10 text-indigo-500",
    },
    {
      icon: Cpu,
      label: "Total tokens",
      value: totals.total_tokens.toLocaleString(),
      tint: "bg-violet-500/10 text-violet-500",
    },
    {
      icon: DollarSign,
      label: "Cost",
      value: `$${totals.cost_usd.toFixed(4)}`,
      hint: "Local models are free",
      tint: "bg-emerald-500/10 text-emerald-500",
    },
    {
      icon: Gauge,
      label: "Avg latency",
      value: formatDuration(totals.avg_duration_ms),
      tint: "bg-cyan-500/10 text-cyan-500",
    },
    {
      icon: TriangleAlert,
      label: "Error rate",
      value: `${(totals.error_rate * 100).toFixed(1)}%`,
      hint: `${totals.errors} error(s)`,
      tint: "bg-amber-500/10 text-amber-500",
    },
  ];
}

export default function AnalyticsPage() {
  const [days, setDays] = useState(30);
  const [metric, setMetric] = useState<UsageMetric>("executions");
  const overview = useAnalyticsOverview(days);
  const data = overview.data;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h1 className="flex items-center gap-2 text-2xl font-semibold tracking-tight">
            <BarChart3 className="size-6 text-primary" />
            Analytics
          </h1>
          <p className="text-muted-foreground">
            AI usage, cost, and performance from your execution audit trail.
          </p>
        </div>
        <div className="flex items-center gap-0.5 rounded-lg border bg-card p-0.5">
          {RANGES.map((range) => (
            <button
              key={range}
              type="button"
              onClick={() => setDays(range)}
              className={cn(
                "rounded-md px-3 py-1 text-sm font-medium transition-colors",
                days === range
                  ? "bg-primary text-primary-foreground"
                  : "text-muted-foreground hover:text-foreground",
              )}
            >
              {range}d
            </button>
          ))}
        </div>
      </div>

      {overview.isPending ? (
        <div className="space-y-4">
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
            {Array.from({ length: 5 }).map((_, i) => (
              <Skeleton key={i} className="h-24 rounded-xl" />
            ))}
          </div>
          <Skeleton className="h-72 rounded-xl" />
        </div>
      ) : data ? (
        <>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
            {tiles(data.totals).map((tile) => (
              <StatTile key={tile.label} {...tile} />
            ))}
          </div>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-base">
                Usage · last {data.days} days
              </CardTitle>
              <div className="flex items-center gap-0.5 rounded-lg border bg-card p-0.5">
                {METRICS.map((m) => (
                  <button
                    key={m.key}
                    type="button"
                    onClick={() => setMetric(m.key)}
                    className={cn(
                      "rounded-md px-2.5 py-1 text-xs font-medium transition-colors",
                      metric === m.key
                        ? "bg-accent text-foreground"
                        : "text-muted-foreground hover:text-foreground",
                    )}
                  >
                    {m.label}
                  </button>
                ))}
              </div>
            </CardHeader>
            <CardContent>
              {data.totals.executions === 0 ? (
                <p className="py-16 text-center text-sm text-muted-foreground">
                  No AI activity in this window yet — chat with the agents to
                  generate some.
                </p>
              ) : (
                <UsageAreaChart points={data.timeseries} metric={metric} />
              )}
            </CardContent>
          </Card>

          <div className="grid gap-4 lg:grid-cols-2">
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-base">Runs by feature</CardTitle>
              </CardHeader>
              <CardContent>
                {data.by_feature.length === 0 ? (
                  <p className="py-16 text-center text-sm text-muted-foreground">
                    No data
                  </p>
                ) : (
                  <FeatureBarChart data={data.by_feature} />
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-base">Tokens by model</CardTitle>
              </CardHeader>
              <CardContent>
                <StatusDonut
                  data={data.by_model.map((m) => ({
                    label: m.model,
                    value: m.total_tokens,
                  }))}
                />
              </CardContent>
            </Card>
          </div>

          <div className="grid gap-4 lg:grid-cols-2">
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-base">Workflow runs</CardTitle>
              </CardHeader>
              <CardContent>
                <StatusDonut
                  data={data.entities.workflow_runs.map((s) => ({
                    label: s.status,
                    value: s.count,
                  }))}
                />
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-base">Tasks by status</CardTitle>
              </CardHeader>
              <CardContent>
                <StatusDonut
                  data={data.entities.tasks.map((s) => ({
                    label: s.status,
                    value: s.count,
                  }))}
                />
              </CardContent>
            </Card>
          </div>
        </>
      ) : null}
    </div>
  );
}
