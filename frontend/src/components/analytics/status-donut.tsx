"use client";

import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";

import {
  DONUT_SEQUENCE,
  ChartTooltip,
} from "@/components/analytics/chart-parts";

export interface DonutSlice {
  label: string;
  value: number;
}

export function StatusDonut({ data }: { data: DonutSlice[] }) {
  const total = data.reduce((sum, slice) => sum + slice.value, 0);
  const rows = data.map((slice) => ({ name: slice.label, value: slice.value }));

  if (total === 0) {
    return (
      <div className="flex h-[220px] items-center justify-center text-sm text-muted-foreground">
        No data yet
      </div>
    );
  }

  return (
    <div className="flex items-center gap-4">
      <ResponsiveContainer width="55%" height={220}>
        <PieChart>
          <Pie
            data={rows}
            dataKey="value"
            nameKey="name"
            innerRadius={55}
            outerRadius={85}
            paddingAngle={2}
            stroke="none"
          >
            {rows.map((_, index) => (
              <Cell
                key={index}
                fill={DONUT_SEQUENCE[index % DONUT_SEQUENCE.length]}
              />
            ))}
          </Pie>
          <Tooltip content={<ChartTooltip formatter={(v) => String(v)} />} />
        </PieChart>
      </ResponsiveContainer>
      <ul className="flex-1 space-y-2">
        {rows.map((row, index) => (
          <li key={row.name} className="flex items-center gap-2 text-sm">
            <span
              className="size-2.5 rounded-full"
              style={{
                backgroundColor: DONUT_SEQUENCE[index % DONUT_SEQUENCE.length],
              }}
            />
            <span className="capitalize text-muted-foreground">{row.name}</span>
            <span className="ml-auto font-medium tabular-nums">
              {row.value}
            </span>
            <span className="w-10 text-right text-xs text-muted-foreground">
              {Math.round((row.value / total) * 100)}%
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
