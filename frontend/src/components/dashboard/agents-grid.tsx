"use client";

import { motion } from "framer-motion";
import {
  BookOpen,
  Bot,
  Globe,
  type LucideIcon,
  ListTodo,
  MessagesSquare,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { useAgents } from "@/features/agents/hooks";
import { useAnalyticsOverview } from "@/features/analytics/hooks";

const ICONS: Record<string, LucideIcon> = {
  knowledge: BookOpen,
  general: MessagesSquare,
  research: Globe,
  planner: ListTodo,
};

export function AgentsGrid() {
  const agents = useAgents();
  const overview = useAnalyticsOverview(30);

  const runsByFeature = new Map(
    (overview.data?.by_feature ?? []).map((f) => [f.feature, f.executions]),
  );

  const items = agents.data ?? [];

  return (
    <Card>
      <CardContent className="p-5">
        <h2 className="mb-4 text-base font-semibold">AI agents</h2>
        {items.length === 0 ? (
          <p className="py-6 text-center text-sm text-muted-foreground">
            No agents registered.
          </p>
        ) : (
          <div className="grid gap-3 sm:grid-cols-2">
            {items.map((agent, index) => {
              const Icon = ICONS[agent.name] ?? Bot;
              const runs = runsByFeature.get(`agent.${agent.name}`) ?? 0;
              return (
                <motion.div
                  key={agent.name}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.25, delay: index * 0.05 }}
                  className="rounded-lg border bg-background/50 p-4 transition-colors hover:border-primary/30"
                >
                  <div className="flex items-start justify-between">
                    <div className="flex size-9 items-center justify-center rounded-lg bg-primary/10 text-primary">
                      <Icon className="size-5" />
                    </div>
                    <Badge variant="success">Ready</Badge>
                  </div>
                  <p className="mt-3 font-medium capitalize">{agent.name}</p>
                  <p className="mt-0.5 line-clamp-2 text-xs text-muted-foreground">
                    {agent.description}
                  </p>
                  <p className="mt-2 text-xs text-muted-foreground">
                    {runs} run{runs === 1 ? "" : "s"} · 30d
                  </p>
                </motion.div>
              );
            })}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
