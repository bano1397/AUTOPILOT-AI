"use client";

import { ChevronDown, Play, Wrench } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { ToolRunner } from "@/components/tools/tool-runner";
import type { ToolInfo } from "@/features/tools/types";
import { cn } from "@/lib/utils";

export function ToolCard({ tool }: { tool: ToolInfo }) {
  const [open, setOpen] = useState(false);
  const inputs = Object.entries(tool.input_schema.properties ?? {});

  return (
    <Card>
      <CardContent className="p-4">
        <div className="flex items-start gap-3">
          <div className="mt-0.5 rounded-lg bg-primary/10 p-2 text-primary">
            <Wrench className="size-4" />
          </div>
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <code className="text-sm font-semibold">{tool.name}</code>
              <Badge variant="secondary">{tool.category}</Badge>
              <Badge variant="outline">
                {tool.origin === "mcp" ? "MCP" : "native"}
              </Badge>
              <span className="text-xs text-muted-foreground">
                v{tool.version}
              </span>
            </div>
            <p className="mt-1 text-sm text-muted-foreground">
              {tool.description}
            </p>

            <dl className="mt-3 grid gap-x-6 gap-y-1 text-xs sm:grid-cols-2">
              <div className="flex gap-1.5">
                <dt className="text-muted-foreground">Inputs</dt>
                <dd className="font-medium">
                  {inputs.length
                    ? inputs.map(([key]) => key).join(", ")
                    : "none"}
                </dd>
              </div>
              <div className="flex gap-1.5">
                <dt className="text-muted-foreground">Depends on</dt>
                <dd className="font-medium">
                  {tool.dependencies.join(", ") || "none"}
                </dd>
              </div>
              <div className="flex gap-1.5 sm:col-span-2">
                <dt className="text-muted-foreground">Declares</dt>
                <dd className="flex flex-wrap gap-1">
                  {tool.permissions.length ? (
                    tool.permissions.map((permission) => (
                      <code
                        key={permission}
                        className="rounded bg-muted px-1 py-0.5"
                      >
                        {permission}
                      </code>
                    ))
                  ) : (
                    <span className="font-medium">no permissions</span>
                  )}
                </dd>
              </div>
            </dl>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={() => setOpen((value) => !value)}
            aria-expanded={open}
          >
            {open ? (
              <ChevronDown className="size-3.5" />
            ) : (
              <Play className="size-3.5" />
            )}
            {open ? "Close" : "Run"}
          </Button>
        </div>

        <div className={cn("mt-4 border-t pt-4", !open && "hidden")}>
          <ToolRunner tool={tool} />
        </div>
      </CardContent>
    </Card>
  );
}
