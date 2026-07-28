import { useMutation, useQuery } from "@tanstack/react-query";

import { invokeTool, listToolCategories, listTools } from "./api";

/** Every registered tool (native today; MCP-adapted tools appear here too). */
export function useTools(category?: string) {
  return useQuery({
    queryKey: ["tools", "list", category ?? "all"],
    queryFn: () => listTools(category),
  });
}

export function useToolCategories() {
  return useQuery({
    queryKey: ["tools", "categories"],
    queryFn: listToolCategories,
  });
}

/** Runs a tool on demand from the marketplace's try-it panel. */
export function useInvokeTool() {
  return useMutation({
    mutationFn: ({
      name,
      args,
    }: {
      name: string;
      args: Record<string, unknown>;
    }) => invokeTool(name, args),
  });
}
