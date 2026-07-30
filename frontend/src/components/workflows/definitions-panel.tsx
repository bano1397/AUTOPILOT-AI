"use client";

import { Copy, GitBranch, Loader2, RotateCcw } from "lucide-react";
import { useEffect, useState } from "react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import {
  useActivateVersion,
  useAddVersion,
  useAgentCatalogue,
  useCloneDefinition,
  useWorkflowDefinition,
  useWorkflowDefinitions,
} from "@/features/workflows/hooks";
import type { GraphSpec, WorkflowVersion } from "@/features/workflows/types";
import { ApiError } from "@/lib/api/types";
import { cn, formatDate } from "@/lib/utils";

function message(error: unknown, fallback: string): string {
  return error instanceof ApiError ? error.message : fallback;
}

export function DefinitionsPanel() {
  const definitions = useWorkflowDefinitions();
  const [selected, setSelected] = useState<string | null>(null);

  const items = definitions.data?.data ?? [];
  const firstId = items[0]?.id;
  useEffect(() => {
    if (!selected && firstId) setSelected(firstId);
  }, [firstId, selected]);

  if (definitions.isPending) {
    return (
      <div className="grid gap-4 lg:grid-cols-[18rem_1fr]">
        <Skeleton className="h-64 rounded-xl" />
        <Skeleton className="h-64 rounded-xl" />
      </div>
    );
  }

  if (items.length === 0) {
    return (
      <div className="flex flex-col items-center gap-2 rounded-2xl border py-20 text-center text-muted-foreground">
        <GitBranch className="size-8" />
        <p className="text-sm">
          No workflow definitions yet — the default one is created the first
          time you message the agents.
        </p>
      </div>
    );
  }

  return (
    <div className="grid gap-4 lg:grid-cols-[18rem_1fr]">
      <div className="space-y-2">
        {items.map((definition) => (
          <button
            key={definition.id}
            type="button"
            onClick={() => setSelected(definition.id)}
            className={cn(
              "w-full rounded-xl border p-3 text-left transition-colors",
              definition.id === selected
                ? "border-primary/40 bg-primary/5"
                : "hover:bg-accent",
            )}
          >
            <p className="truncate text-sm font-medium">{definition.name}</p>
            <p className="line-clamp-2 text-xs text-muted-foreground">
              {definition.description || "No description"}
            </p>
            {definition.cloned_from_id && (
              <Badge variant="outline" className="mt-1.5 text-[10px]">
                cloned
              </Badge>
            )}
          </button>
        ))}
      </div>

      <div className="rounded-2xl border bg-card p-5">
        {selected ? (
          <DefinitionDetail definitionId={selected} />
        ) : (
          <p className="py-16 text-center text-sm text-muted-foreground">
            Select a workflow.
          </p>
        )}
      </div>
    </div>
  );
}

function DefinitionDetail({ definitionId }: { definitionId: string }) {
  const detail = useWorkflowDefinition(definitionId);
  const clone = useCloneDefinition(definitionId);
  const [cloneName, setCloneName] = useState("");

  if (detail.isPending) {
    return (
      <div className="flex items-center gap-2 py-16 text-sm text-muted-foreground">
        <Loader2 className="size-4 animate-spin" /> Loading workflow…
      </div>
    );
  }
  if (detail.isError || !detail.data) {
    return (
      <p className="py-16 text-center text-sm text-destructive">
        Unable to load this workflow.
      </p>
    );
  }

  const { definition, versions, active_version: active } = detail.data;

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold">{definition.name}</h2>
        <p className="text-sm text-muted-foreground">
          {definition.description || "No description"}
        </p>
      </div>

      {active && (
        <NewVersionForm
          definitionId={definitionId}
          current={active.graph_spec}
        />
      )}

      <div className="space-y-2">
        <h3 className="text-sm font-medium">
          Versions{" "}
          <span className="text-muted-foreground">
            — immutable; activating an older one is a rollback
          </span>
        </h3>
        {[...versions].reverse().map((version) => (
          <VersionRow key={version.id} version={version} />
        ))}
      </div>

      <div className="space-y-2 border-t pt-4">
        <h3 className="text-sm font-medium">Clone</h3>
        <p className="text-xs text-muted-foreground">
          Forks this workflow, seeding v1 from its <em>active</em> version.
        </p>
        <div className="flex gap-2">
          <Input
            value={cloneName}
            onChange={(event) => setCloneName(event.target.value)}
            placeholder="new-workflow-name"
            className="max-w-xs"
          />
          <Button
            variant="outline"
            disabled={!cloneName.trim() || clone.isPending}
            onClick={() =>
              clone.mutate(cloneName.trim(), {
                onSuccess: () => {
                  toast.success(`Cloned to “${cloneName.trim()}”`);
                  setCloneName("");
                },
                onError: (error) => toast.error(message(error, "Clone failed")),
              })
            }
          >
            {clone.isPending ? (
              <Loader2 className="mr-1.5 size-4 animate-spin" />
            ) : (
              <Copy className="mr-1.5 size-4" />
            )}
            Clone
          </Button>
        </div>
      </div>
    </div>
  );
}

function VersionRow({ version }: { version: WorkflowVersion }) {
  const activate = useActivateVersion();
  const spec = version.graph_spec;

  return (
    <div
      className={cn(
        "rounded-xl border p-3",
        version.is_active && "border-emerald-500/40 bg-emerald-500/5",
      )}
    >
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-sm font-medium">v{version.version}</span>
        {version.is_active ? (
          <Badge variant="success">Active</Badge>
        ) : (
          <Button
            variant="outline"
            size="sm"
            disabled={activate.isPending}
            onClick={() =>
              activate.mutate(version.id, {
                onSuccess: () =>
                  toast.success(`v${version.version} is now active`),
                onError: (error) =>
                  toast.error(message(error, "Activation failed")),
              })
            }
          >
            <RotateCcw className="mr-1.5 size-3.5" />
            Activate
          </Button>
        )}
        <span className="ml-auto text-xs text-muted-foreground">
          {formatDate(version.created_at)}
        </span>
      </div>

      {version.notes && (
        <p className="mt-1.5 text-xs text-muted-foreground">{version.notes}</p>
      )}

      <div className="mt-2 flex flex-wrap gap-1.5">
        {spec.agents.map((agent) => (
          <Badge key={agent} variant="secondary" className="text-[10px]">
            {agent}
            {agent === spec.fallback_agent && " ·  fallback"}
          </Badge>
        ))}
        <Badge
          variant={spec.approval_gate ? "outline" : "destructive"}
          className="text-[10px]"
        >
          {spec.approval_gate ? "approval gate" : "no approval gate"}
        </Badge>
      </div>
    </div>
  );
}

function NewVersionForm({
  definitionId,
  current,
}: {
  definitionId: string;
  current: GraphSpec;
}) {
  const catalogue = useAgentCatalogue();
  const addVersion = useAddVersion(definitionId);

  const [agents, setAgents] = useState<string[]>(current.agents);
  const [fallback, setFallback] = useState(current.fallback_agent);
  const [gate, setGate] = useState(current.approval_gate);
  const [notes, setNotes] = useState("");

  const available = catalogue.data?.agents ?? current.agents;
  // The server rejects a fallback outside the agent list. Rather than leave the
  // form in a state the user has to notice and repair, deselecting the current
  // fallback moves it to another selected agent.
  useEffect(() => {
    if (agents.length > 0 && !agents.includes(fallback)) {
      setFallback(agents[0]);
    }
  }, [agents, fallback]);

  const fallbackValid = agents.includes(fallback);
  const changed =
    JSON.stringify([...agents].sort()) !==
      JSON.stringify([...current.agents].sort()) ||
    fallback !== current.fallback_agent ||
    gate !== current.approval_gate;

  function toggle(agent: string) {
    setAgents((currentAgents) =>
      currentAgents.includes(agent)
        ? currentAgents.filter((name) => name !== agent)
        : [...currentAgents, agent],
    );
  }

  return (
    <div className="space-y-3 rounded-xl border bg-muted/30 p-4">
      <h3 className="text-sm font-medium">New version</h3>
      <p className="text-xs text-muted-foreground">
        Versions are never edited. Publishing appends v{"{next}"} and makes it
        live.
      </p>

      <div>
        <p className="mb-1.5 text-xs font-medium">
          Agents the supervisor may route to
        </p>
        <div className="flex flex-wrap gap-1.5">
          {available.map((agent) => (
            <button
              key={agent}
              type="button"
              onClick={() => toggle(agent)}
              className={cn(
                "rounded-full border px-2.5 py-1 text-xs transition-colors",
                agents.includes(agent)
                  ? "border-primary/40 bg-primary/10 text-foreground"
                  : "text-muted-foreground hover:bg-accent",
              )}
            >
              {agent}
            </button>
          ))}
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-4">
        <label className="flex items-center gap-2 text-xs">
          Fallback
          <select
            value={fallback}
            onChange={(event) => setFallback(event.target.value)}
            className="rounded-md border bg-background px-2 py-1 text-xs"
          >
            {agents.map((agent) => (
              <option key={agent} value={agent}>
                {agent}
              </option>
            ))}
          </select>
        </label>

        <label className="flex cursor-pointer items-center gap-2 text-xs">
          <input
            type="checkbox"
            checked={gate}
            onChange={(event) => setGate(event.target.checked)}
          />
          Approval gate
        </label>

        <Input
          value={notes}
          onChange={(event) => setNotes(event.target.value)}
          placeholder="What changed?"
          className="h-8 max-w-xs text-xs"
        />
      </div>

      {agents.length === 0 && (
        <p className="text-xs text-destructive">
          A workflow needs at least one agent.
        </p>
      )}
      {agents.length > 0 && !fallbackValid && (
        <p className="text-xs text-destructive">
          The fallback must be one of the selected agents.
        </p>
      )}

      <Button
        size="sm"
        disabled={
          !changed ||
          agents.length === 0 ||
          !fallbackValid ||
          addVersion.isPending
        }
        onClick={() =>
          addVersion.mutate(
            {
              graphSpec: {
                topology: current.topology,
                agents,
                fallback_agent: fallback,
                approval_gate: gate,
              },
              notes,
              activate: true,
            },
            {
              onSuccess: (version) => {
                toast.success(`Published v${version.version}`);
                setNotes("");
              },
              onError: (error) =>
                toast.error(message(error, "Could not publish version")),
            },
          )
        }
      >
        {addVersion.isPending && (
          <Loader2 className="mr-1.5 size-4 animate-spin" />
        )}
        Publish new version
      </Button>
    </div>
  );
}
