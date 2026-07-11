"use client";

import { motion } from "framer-motion";
import {
  ArrowDownRight,
  ArrowUpRight,
  type LucideIcon,
  Minus,
} from "lucide-react";

import { Sparkline } from "@/components/dashboard/sparkline";
import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";

const TONES = {
  indigo: {
    text: "text-indigo-600 dark:text-indigo-400",
    bg: "bg-indigo-500/10",
    hex: "#6366f1",
  },
  violet: {
    text: "text-violet-600 dark:text-violet-400",
    bg: "bg-violet-500/10",
    hex: "#8b5cf6",
  },
  emerald: {
    text: "text-emerald-600 dark:text-emerald-400",
    bg: "bg-emerald-500/10",
    hex: "#10b981",
  },
  amber: {
    text: "text-amber-600 dark:text-amber-400",
    bg: "bg-amber-500/10",
    hex: "#f59e0b",
  },
} as const;

export type KpiTone = keyof typeof TONES;

/** Trend over a series: recent half vs the prior half. */
function computeTrend(series: number[]): number | null {
  if (series.length < 4) return null;
  const mid = Math.floor(series.length / 2);
  const prev = series.slice(0, mid).reduce((a, b) => a + b, 0);
  const recent = series.slice(mid).reduce((a, b) => a + b, 0);
  if (prev === 0) return recent > 0 ? 100 : 0;
  return Math.round(((recent - prev) / prev) * 100);
}

export function KpiCard({
  id,
  label,
  value,
  hint,
  icon: Icon,
  tone,
  series,
  index = 0,
}: {
  id: string;
  label: string;
  value: string;
  hint?: string;
  icon: LucideIcon;
  tone: KpiTone;
  series?: number[];
  index?: number;
}) {
  const t = TONES[tone];
  const trend = series ? computeTrend(series) : null;
  const TrendIcon =
    trend === null || trend === 0
      ? Minus
      : trend > 0
        ? ArrowUpRight
        : ArrowDownRight;
  const trendColor =
    trend === null || trend === 0
      ? "text-muted-foreground"
      : trend > 0
        ? "text-emerald-600 dark:text-emerald-400"
        : "text-rose-600 dark:text-rose-400";

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, delay: index * 0.06 }}
      whileHover={{ y: -3 }}
    >
      <Card className="overflow-hidden transition-shadow hover:shadow-lg">
        <CardContent className="p-5">
          <div className="flex items-start justify-between">
            <div className="space-y-1">
              <p className="text-sm text-muted-foreground">{label}</p>
              <p className="text-2xl font-semibold tabular-nums tracking-tight">
                {value}
              </p>
            </div>
            <div
              className={cn(
                "flex size-9 items-center justify-center rounded-xl",
                t.bg,
                t.text,
              )}
            >
              <Icon className="size-5" />
            </div>
          </div>

          <div className="mt-3 flex items-end justify-between gap-3">
            <div className="flex items-center gap-1 text-xs">
              {trend !== null ? (
                <>
                  <TrendIcon className={cn("size-3.5", trendColor)} />
                  <span className={trendColor}>{Math.abs(trend)}%</span>
                  <span className="text-muted-foreground">vs prior</span>
                </>
              ) : (
                <span className="text-muted-foreground">{hint ?? ""}</span>
              )}
            </div>
            {series && series.length > 1 && (
              <div className="h-11 w-24 shrink-0">
                <Sparkline id={id} data={series} color={t.hex} />
              </div>
            )}
          </div>
        </CardContent>
      </Card>
    </motion.div>
  );
}
