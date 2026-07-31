"use client";

import { Bot, ClipboardCheck, Cpu, FileText } from "lucide-react";

import { ActivityFeed } from "@/components/dashboard/activity-feed";
import { AgentsGrid } from "@/components/dashboard/agents-grid";
import { AssistantLauncher } from "@/components/dashboard/assistant-launcher";
import { GreetingHero } from "@/components/dashboard/greeting-hero";
import { KpiCard } from "@/components/dashboard/kpi-card";
import { StatusBanner } from "@/components/dashboard/status-banner";
import { useDashboard } from "@/features/dashboard/hooks";
import { formatDuration } from "@/lib/utils";

export default function DashboardPage() {
  // One call instead of three: see useDashboard.
  const dashboard = useDashboard(30);
  const overview = dashboard.data?.analytics;

  const totals = overview?.totals;
  const timeseries = overview?.timeseries ?? [];
  const documentsIndexed = overview?.entities.documents_indexed ?? 0;
  const pending = dashboard.data?.pending_approval_count ?? 0;
  const agentCount = dashboard.data?.agents.length ?? 0;

  const execSeries = timeseries.map((point) => point.executions);
  const tokenSeries = timeseries.map((point) => point.total_tokens);

  const health = dashboard.isError
    ? "unreachable"
    : dashboard.isPending
      ? "connecting"
      : "operational";

  return (
    <div className="space-y-6">
      <GreetingHero />

      <StatusBanner
        health={health}
        agents={agentCount.toString()}
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
          <AgentsGrid
            agents={dashboard.data?.agents ?? []}
            byFeature={overview?.by_feature ?? []}
          />
        </div>
        <ActivityFeed runs={dashboard.data?.recent_runs ?? []} />
      </div>
    </div>
  );
}
