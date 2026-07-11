"use client";

import { Area, AreaChart, ResponsiveContainer } from "recharts";

/** A tiny, axis-free trend line for KPI cards. */
export function Sparkline({
  id,
  data,
  color,
}: {
  id: string;
  data: number[];
  color: string;
}) {
  const points = data.map((value, index) => ({ index, value }));
  return (
    <ResponsiveContainer width="100%" height={44}>
      <AreaChart
        data={points}
        margin={{ top: 4, right: 0, left: 0, bottom: 0 }}
      >
        <defs>
          <linearGradient id={`spark-${id}`} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={color} stopOpacity={0.35} />
            <stop offset="100%" stopColor={color} stopOpacity={0} />
          </linearGradient>
        </defs>
        <Area
          type="monotone"
          dataKey="value"
          stroke={color}
          strokeWidth={2}
          fill={`url(#spark-${id})`}
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}
