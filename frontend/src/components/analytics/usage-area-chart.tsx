"use client";

import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import {
  AXIS_COLOR,
  CHART_COLORS,
  ChartTooltip,
} from "@/components/analytics/chart-parts";
import type { TimeseriesPoint } from "@/features/analytics/types";

export type UsageMetric = "executions" | "total_tokens" | "cost_usd";

const METRIC_COLOR: Record<UsageMetric, string> = {
  executions: CHART_COLORS.indigo,
  total_tokens: CHART_COLORS.violet,
  cost_usd: CHART_COLORS.emerald,
};

const METRIC_LABEL: Record<UsageMetric, string> = {
  executions: "Executions",
  total_tokens: "Tokens",
  cost_usd: "Cost (USD)",
};

function shortDate(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return `${d.getMonth() + 1}/${d.getDate()}`;
}

export function UsageAreaChart({
  points,
  metric,
}: {
  points: TimeseriesPoint[];
  metric: UsageMetric;
}) {
  const color = METRIC_COLOR[metric];
  const data = points.map((p) => ({ ...p, date: shortDate(p.date) }));

  return (
    <ResponsiveContainer width="100%" height={260}>
      <AreaChart
        data={data}
        margin={{ top: 8, right: 8, left: -12, bottom: 0 }}
      >
        <defs>
          <linearGradient id={`usage-${metric}`} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={color} stopOpacity={0.35} />
            <stop offset="100%" stopColor={color} stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid
          strokeDasharray="3 3"
          stroke={AXIS_COLOR}
          strokeOpacity={0.15}
          vertical={false}
        />
        <XAxis
          dataKey="date"
          tick={{ fontSize: 11, fill: AXIS_COLOR }}
          tickLine={false}
          axisLine={false}
          minTickGap={24}
        />
        <YAxis
          tick={{ fontSize: 11, fill: AXIS_COLOR }}
          tickLine={false}
          axisLine={false}
          width={44}
        />
        <Tooltip
          content={
            <ChartTooltip
              formatter={(value) =>
                metric === "cost_usd"
                  ? `$${Number(value).toFixed(4)}`
                  : Number(value).toLocaleString()
              }
            />
          }
        />
        <Area
          type="monotone"
          dataKey={metric}
          name={METRIC_LABEL[metric]}
          stroke={color}
          strokeWidth={2}
          fill={`url(#usage-${metric})`}
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}
