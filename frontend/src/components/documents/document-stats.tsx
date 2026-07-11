"use client";

import { Boxes, CheckCircle2, Database, type LucideIcon } from "lucide-react";

import { useAnalyticsOverview } from "@/features/analytics/hooks";
import { useDocuments } from "@/features/documents/hooks";
import { cn } from "@/lib/utils";

function Stat({
  icon: Icon,
  label,
  value,
  tint,
}: {
  icon: LucideIcon;
  label: string;
  value: string;
  tint: string;
}) {
  return (
    <div className="flex items-center gap-3 rounded-xl border bg-card p-4">
      <div
        className={cn(
          "flex size-10 items-center justify-center rounded-lg",
          tint,
        )}
      >
        <Icon className="size-5" />
      </div>
      <div>
        <p className="text-xl font-semibold tabular-nums tracking-tight">
          {value}
        </p>
        <p className="text-xs text-muted-foreground">{label}</p>
      </div>
    </div>
  );
}

export function DocumentStats() {
  const docs = useDocuments(1);
  const overview = useAnalyticsOverview(30);

  const total = docs.data?.meta?.total ?? 0;
  const indexed = overview.data?.entities.documents_indexed ?? 0;

  return (
    <div className="grid gap-3 sm:grid-cols-3">
      <Stat
        icon={Boxes}
        label="Total documents"
        value={total.toLocaleString()}
        tint="text-indigo-500 bg-indigo-500/10"
      />
      <Stat
        icon={CheckCircle2}
        label="Indexed & searchable"
        value={indexed.toLocaleString()}
        tint="text-emerald-500 bg-emerald-500/10"
      />
      <Stat
        icon={Database}
        label="Vector store — ChromaDB · nomic-embed-text"
        value="Connected"
        tint="text-cyan-500 bg-cyan-500/10"
      />
    </div>
  );
}
