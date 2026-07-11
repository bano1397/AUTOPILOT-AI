import { apiFetch } from "@/lib/api/client";

import type { RagAskResult, RagQueryResult } from "./types";

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
