"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import {
  AXIS_COLOR,
  DONUT_SEQUENCE,
  ChartTooltip,
} from "@/components/analytics/chart-parts";
import type { FeatureStat } from "@/features/analytics/types";

export function FeatureBarChart({ data }: { data: FeatureStat[] }) {
  const rows = [...data]
    .sort((a, b) => b.executions - a.executions)
    .slice(0, 8)
    .map((f) => ({ feature: f.feature, executions: f.executions }));

  return (
    <ResponsiveContainer width="100%" height={260}>
      <BarChart
        data={rows}
        layout="vertical"
        margin={{ top: 4, right: 12, left: 8, bottom: 0 }}
      >
        <CartesianGrid
          strokeDasharray="3 3"
          stroke={AXIS_COLOR}
          strokeOpacity={0.15}
          horizontal={false}
        />
        <XAxis
          type="number"
          tick={{ fontSize: 11, fill: AXIS_COLOR }}
          tickLine={false}
          axisLine={false}
          allowDecimals={false}
        />
        <YAxis
          type="category"
          dataKey="feature"
          tick={{ fontSize: 11, fill: AXIS_COLOR }}
          tickLine={false}
          axisLine={false}
          width={110}
        />
        <Tooltip
          cursor={{ fill: AXIS_COLOR, fillOpacity: 0.08 }}
          content={
            <ChartTooltip formatter={(v) => Number(v).toLocaleString()} />
          }
        />
        <Bar dataKey="executions" name="Runs" radius={[0, 4, 4, 0]}>
          {rows.map((_, index) => (
            <Cell
              key={index}
              fill={DONUT_SEQUENCE[index % DONUT_SEQUENCE.length]}
            />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
