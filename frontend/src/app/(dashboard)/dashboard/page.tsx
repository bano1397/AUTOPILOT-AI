"use client";

import { Bot, ClipboardCheck, Cpu, FileText } from "lucide-react";

import { ActivityFeed } from "@/components/dashboard/activity-feed";
import { AgentsGrid } from "@/components/dashboard/agents-grid";
import { AssistantLauncher } from "@/components/dashboard/assistant-launcher";
import { GreetingHero } from "@/components/dashboard/greeting-hero";
import { KpiCard } from "@/components/dashboard/kpi-card";
import { StatusBanner } from "@/components/dashboard/status-banner";
import { useAgents } from "@/features/agents/hooks";
import { useAnalyticsOverview } from "@/features/analytics/hooks";
import { usePendingApprovals } from "@/features/approvals/hooks";
import { formatDuration } from "@/lib/utils";

export default function DashboardPage() {
  const overview = useAnalyticsOverview(30);
  const approvals = usePendingApprovals(1);
  const agents = useAgents();

  const totals = overview.data?.totals;
  const timeseries = overview.data?.timeseries ?? [];
  const documentsIndexed = overview.data?.entities.documents_indexed ?? 0;
  const pending = approvals.data?.meta?.total ?? 0;

  const execSeries = timeseries.map((point) => point.executions);
  const tokenSeries = timeseries.map((point) => point.total_tokens);

  const health = overview.isError
    ? "unreachable"
    : overview.isPending
      ? "connecting"
      : "operational";

  return (
    <div className="space-y-6">
      <GreetingHero />

      <StatusBanner
        health={health}
        agents={(agents.data?.length ?? 0).toString()}
        runs={(totals?.executions ?? 0).toLocaleString()}
        avgLatency={formatDuration(totals?.avg_duration_ms ?? 0)}
        approvals={pending.toString()}
      />

      <AssistantLauncher />

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <KpiCard
          id="runs"
          label="AI runs · 30d"
          value={(totals?.executions ?? 0).toLocaleString()}
          icon={Bot}
          tone="indigo"
          series={execSeries}
          index={0}
        />
        <KpiCard
          id="tokens"
          label="Tokens · 30d"
          value={(totals?.total_tokens ?? 0).toLocaleString()}
          icon={Cpu}
          tone="violet"
          series={tokenSeries}
          index={1}
        />
        <KpiCard
          id="docs"
          label="Documents indexed"
          value={documentsIndexed.toLocaleString()}
          icon={FileText}
          tone="emerald"
          hint="Searchable knowledge"
          index={2}
        />
        <KpiCard
          id="approvals"
          label="Pending approvals"
          value={pending.toLocaleString()}
          icon={ClipboardCheck}
          tone="amber"
          hint={pending > 0 ? "Action needed" : "All clear"}
          index={3}
        />
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <AgentsGrid />
        </div>
        <ActivityFeed />
      </div>
    </div>
  );
}
