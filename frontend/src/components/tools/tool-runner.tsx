"use client";

import { Loader2 } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useInvokeTool } from "@/features/tools/hooks";
import type { ToolInfo } from "@/features/tools/types";
import { ApiError } from "@/lib/api/types";

/**
 * Renders a form from the tool's own JSON Schema and invokes it. Deliberately
 * minimal — string/number/boolean inputs only, which covers every native tool.
 * Values are sent as typed JSON so backend validation sees the right types.
 */
export function ToolRunner({ tool }: { tool: ToolInfo }) {
  const properties = tool.input_schema.properties ?? {};
  const required = new Set(tool.input_schema.required ?? []);
  const [values, setValues] = useState<Record<string, string>>({});
  const invoke = useInvokeTool();

  const coerce = (key: string, raw: string): unknown => {
    const type = properties[key]?.type;
    if (type === "integer" || type === "number") return Number(raw);
    if (type === "boolean") return raw === "true";
    return raw;
  };

  const submit = () => {
    const args: Record<string, unknown> = {};
    for (const [key, raw] of Object.entries(values)) {
      if (raw !== "") args[key] = coerce(key, raw);
    }
    invoke.mutate({ name: tool.name, args });
  };

  const error =
    invoke.error instanceof ApiError
      ? invoke.error.message
      : invoke.error
        ? "Invocation failed."
        : null;

  return (
    <div className="space-y-3">
      <div className="grid gap-3 sm:grid-cols-2">
        {Object.entries(properties).map(([key, schema]) => (
          <div key={key} className="space-y-1.5">
            <Label htmlFor={`${tool.name}-${key}`} className="text-xs">
              {key}
              {required.has(key) && (
                <span className="ml-0.5 text-destructive">*</span>
              )}
              {schema.type && (
                <span className="ml-1.5 font-normal text-muted-foreground">
                  {schema.type}
                </span>
              )}
            </Label>
            <Input
              id={`${tool.name}-${key}`}
              value={values[key] ?? ""}
              placeholder={
                schema.default !== undefined ? String(schema.default) : ""
              }
              onChange={(event) =>
                setValues((prev) => ({ ...prev, [key]: event.target.value }))
              }
            />
          </div>
        ))}
      </div>

      <Button size="sm" onClick={submit} disabled={invoke.isPending}>
        {invoke.isPending && <Loader2 className="size-3.5 animate-spin" />}
        Invoke
      </Button>

      {error && (
        <p role="alert" className="text-sm text-destructive">
          {error}
        </p>
      )}

      {invoke.data && (
        <pre className="max-h-64 overflow-auto rounded-lg bg-muted p-3 text-xs">
          {JSON.stringify(invoke.data.result, null, 2)}
        </pre>
      )}
    </div>
  );
}
