"use client";

import type { ReactNode } from "react";

/** Brand palette for chart series (theme-independent, high-contrast on cards). */
export const CHART_COLORS = {
  indigo: "#6366f1",
  violet: "#8b5cf6",
  cyan: "#06b6d4",
  emerald: "#10b981",
  amber: "#f59e0b",
  rose: "#ef4444",
} as const;

export const DONUT_SEQUENCE = [
  CHART_COLORS.indigo,
  CHART_COLORS.violet,
  CHART_COLORS.cyan,
  CHART_COLORS.emerald,
  CHART_COLORS.amber,
  CHART_COLORS.rose,
];

/** Muted axis/grid color that reads well in both themes. */
export const AXIS_COLOR = "#94a3b8";

interface TooltipEntry {
  name?: string;
  value?: number | string;
  color?: string;
}

/** Themed tooltip card for Recharts (uses design-system tokens). */
export function ChartTooltip({
  active,
  payload,
  label,
  formatter,
}: {
  active?: boolean;
  payload?: TooltipEntry[];
  label?: ReactNode;
  formatter?: (value: number | string, name?: string) => string;
}) {
  if (!active || !payload || payload.length === 0) return null;
  return (
    <div className="rounded-lg border bg-popover px-3 py-2 text-xs shadow-lg">
      {label != null && <p className="mb-1 font-medium">{label}</p>}
      {payload.map((entry, index) => (
        <div key={index} className="flex items-center gap-2">
          <span
            className="size-2 rounded-full"
            style={{ backgroundColor: entry.color }}
          />
          <span className="text-muted-foreground">{entry.name}</span>
          <span className="ml-auto font-medium tabular-nums">
            {formatter && entry.value != null
              ? formatter(entry.value, entry.name)
              : entry.value}
          </span>
        </div>
      ))}
    </div>
  );
}
