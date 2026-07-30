import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";

import { API_URL } from "@/lib/config";

import {
  activateVersion,
  addVersion,
  cloneDefinition,
  getDefinition,
  getWorkflowRun,
  listAgentCatalogue,
  listDefinitions,
  listWorkflowRuns,
} from "./api";
import type { GraphSpec, RunEvent } from "./types";

export const WORKFLOW_RUNS_KEY = ["workflow-runs"];

export function useWorkflowRuns(page: number, pageSize = 10) {
  return useQuery({
    queryKey: [...WORKFLOW_RUNS_KEY, page, pageSize],
    queryFn: () => listWorkflowRuns(page, pageSize),
  });
}

/** Run detail (steps + payloads); fetched lazily when a row is expanded. */
export function useWorkflowRun(id: string | null) {
  return useQuery({
    queryKey: [...WORKFLOW_RUNS_KEY, "detail", id],
    queryFn: () => getWorkflowRun(id as string),
    enabled: id !== null,
  });
}

export const WORKFLOW_DEFS_KEY = ["workflow-definitions"];

export function useWorkflowDefinitions() {
  return useQuery({
    queryKey: WORKFLOW_DEFS_KEY,
    queryFn: listDefinitions,
  });
}

export function useWorkflowDefinition(id: string | null) {
  return useQuery({
    queryKey: [...WORKFLOW_DEFS_KEY, id],
    queryFn: () => getDefinition(id as string),
    enabled: id !== null,
  });
}

export function useAgentCatalogue() {
  return useQuery({
    queryKey: ["workflow-agent-catalogue"],
    queryFn: listAgentCatalogue,
    staleTime: 5 * 60 * 1000,
  });
}

/** Invalidate everything a version change can affect: the definition's version
 *  list, and the run list (subsequent runs pin a different version). */
function useWorkflowInvalidator() {
  const queryClient = useQueryClient();
  return () => {
    void queryClient.invalidateQueries({ queryKey: WORKFLOW_DEFS_KEY });
    void queryClient.invalidateQueries({ queryKey: WORKFLOW_RUNS_KEY });
  };
}

export function useAddVersion(definitionId: string) {
  const invalidate = useWorkflowInvalidator();
  return useMutation({
    mutationFn: (input: {
      graphSpec: GraphSpec;
      notes: string;
      activate: boolean;
    }) =>
      addVersion(definitionId, input.graphSpec, input.notes, input.activate),
    onSuccess: invalidate,
  });
}

export function useActivateVersion() {
  const invalidate = useWorkflowInvalidator();
  return useMutation({
    mutationFn: (versionId: string) => activateVersion(versionId),
    onSuccess: invalidate,
  });
}

export function useCloneDefinition(definitionId: string) {
  const invalidate = useWorkflowInvalidator();
  return useMutation({
    mutationFn: (name: string) => cloneDefinition(definitionId, name),
    onSuccess: invalidate,
  });
}

const MAX_LIVE_EVENTS = 50;

/**
 * Live workflow status over the `/ws/runs` WebSocket.
 *
 * Keeps only the most recent events: this is a status ticker, not a log store,
 * and an unbounded array on a long-lived page is a leak. Reconnects on close
 * with a fixed delay — the server is the same origin as the API, so a failure
 * here means the backend is down and hammering it would not help.
 */
export function useLiveRunEvents(enabled = true) {
  const [events, setEvents] = useState<RunEvent[]>([]);
  const [connected, setConnected] = useState(false);
  const socketRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    if (!enabled || typeof window === "undefined") return;

    let closed = false;
    let retry: ReturnType<typeof setTimeout> | undefined;

    const connect = () => {
      if (closed) return;
      const url = `${API_URL.replace(/^http/, "ws")}/ws/runs`;
      const socket = new WebSocket(url);
      socketRef.current = socket;

      socket.onopen = () => setConnected(true);
      socket.onclose = () => {
        setConnected(false);
        if (!closed) retry = setTimeout(connect, 3000);
      };
      // onerror is always followed by onclose, which owns the retry.
      socket.onerror = () => socket.close();
      socket.onmessage = (message) => {
        try {
          const event = JSON.parse(message.data as string) as RunEvent;
          // Keepalives keep the socket open; they are not status.
          if (event.type === "ping") return;
          setEvents((current) => [...current, event].slice(-MAX_LIVE_EVENTS));
        } catch {
          // A frame we cannot parse is not worth breaking the ticker over.
        }
      };
    };

    connect();
    return () => {
      closed = true;
      if (retry) clearTimeout(retry);
      socketRef.current?.close();
    };
  }, [enabled]);

  return { events, connected };
}
