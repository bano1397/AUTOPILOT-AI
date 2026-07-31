import { apiFetch } from "@/lib/api/client";
import { API_URL } from "@/lib/config";

import type { RagAskResult, RagMatch, RagQueryResult } from "./types";

export function ragQuery(query: string, topK = 5): Promise<RagQueryResult> {
  return apiFetch<RagQueryResult>("/api/v1/rag/query", {
    method: "POST",
    body: { query, top_k: topK },
  });
}

export function ragAsk(query: string, topK = 5): Promise<RagAskResult> {
  return apiFetch<RagAskResult>("/api/v1/rag/ask", {
    method: "POST",
    body: { query, top_k: topK },
  });
}

/** A frame from `POST /api/v1/rag/ask/stream`. */
export type AskStreamEvent =
  | { event: "sources"; data: RagMatch[] }
  | { event: "delta"; data: string }
  | { event: "done"; data: { grounded: boolean; model: string | null } }
  | { event: "error"; data: string };

/**
 * Stream a grounded answer as Server-Sent Events.
 *
 * Hand-rolled rather than using `EventSource`, which only speaks GET and
 * cannot send a JSON body. Frames are split on the blank-line delimiter and a
 * partial tail is carried into the next read, because a chunk boundary can
 * land anywhere — including mid-frame.
 */
export async function* ragAskStream(
  query: string,
  topK?: number,
  signal?: AbortSignal,
): AsyncGenerator<AskStreamEvent> {
  const response = await fetch(`${API_URL}/api/v1/rag/ask/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query, top_k: topK }),
    signal,
  });

  if (!response.ok || !response.body) {
    throw new Error(`Streaming request failed (${response.status})`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  try {
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      let boundary = buffer.indexOf("\n\n");
      while (boundary !== -1) {
        const frame = buffer.slice(0, boundary);
        buffer = buffer.slice(boundary + 2);
        const parsed = parseFrame(frame);
        if (parsed) yield parsed;
        boundary = buffer.indexOf("\n\n");
      }
    }
  } finally {
    // Releasing matters on abort: without it the connection stays open until
    // the tab is closed.
    reader.releaseLock();
  }
}

function parseFrame(frame: string): AskStreamEvent | null {
  let event = "";
  let data = "";
  for (const line of frame.split("\n")) {
    if (line.startsWith("event:")) event = line.slice(6).trim();
    else if (line.startsWith("data:")) data += line.slice(5).trim();
  }
  if (!event || !data) return null;
  try {
    return { event, data: JSON.parse(data) } as AskStreamEvent;
  } catch {
    return null;
  }
}
