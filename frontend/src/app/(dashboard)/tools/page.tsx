"use client";

import { useState } from "react";

import { ToolCard } from "@/components/tools/tool-card";
import { Skeleton } from "@/components/ui/skeleton";
import { useToolCategories, useTools } from "@/features/tools/hooks";
import { API_URL } from "@/lib/config";
import { cn } from "@/lib/utils";

export default function ToolsPage() {
  const [category, setCategory] = useState<string | undefined>();
  const tools = useTools(category);
  const categories = useToolCategories();

  const filters = [
    { key: undefined, label: "All" },
    ...(categories.data ?? []).map((value) => ({ key: value, label: value })),
  ];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Tools</h1>
        <p className="text-muted-foreground">
          Every capability registered on the platform. Agents select tools by
          category and capability, so anything listed here is callable by them —
          and by you, from the Run panel.
        </p>
      </div>

      <div className="rounded-lg border bg-card p-3 text-sm">
        <p className="font-medium">Usable from outside, too</p>
        <p className="mt-0.5 text-muted-foreground">
          These tools are exposed over the Model Context Protocol. Point an MCP
          client at{" "}
          <code className="rounded bg-muted px-1.5 py-0.5 text-xs">
            {API_URL}/api/v1/tools/mcp
          </code>{" "}
          to call them by JSON-RPC. Tools imported from external MCP servers
          appear below with an <span className="font-medium">MCP</span> badge.
        </p>
      </div>

      <div className="flex flex-wrap items-center gap-1">
        {filters.map((filter) => (
          <button
            key={filter.label}
            type="button"
            onClick={() => setCategory(filter.key)}
            className={cn(
              "rounded-lg px-3 py-1.5 text-sm font-medium capitalize transition-colors",
              category === filter.key
                ? "bg-primary/10 text-primary"
                : "text-muted-foreground hover:bg-accent hover:text-foreground",
            )}
          >
            {filter.label}
          </button>
        ))}
      </div>

      {tools.isLoading ? (
        <div className="space-y-3">
          {[0, 1, 2].map((key) => (
            <Skeleton key={key} className="h-32 w-full" />
          ))}
        </div>
      ) : tools.isError ? (
        <p role="alert" className="text-sm text-destructive">
          Could not load the tool registry.
        </p>
      ) : tools.data?.length ? (
        <div className="space-y-3">
          {tools.data.map((tool) => (
            <ToolCard key={tool.name} tool={tool} />
          ))}
        </div>
      ) : (
        <p className="text-sm text-muted-foreground">No tools registered.</p>
      )}
    </div>
  );
}
