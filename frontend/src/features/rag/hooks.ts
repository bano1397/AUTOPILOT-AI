import { useMutation } from "@tanstack/react-query";
import { useCallback, useRef, useState } from "react";

import { useChatStore } from "@/lib/chat/store";

import { ragAsk, ragAskStream, ragQuery } from "./api";
import type { RagMatch } from "./types";

/** Runs a semantic search on demand (a mutation so nothing fires on mount). */
export function useRagQuery() {
  return useMutation({
    mutationFn: ({ query, topK }: { query: string; topK?: number }) =>
      ragQuery(query, topK),
  });
}

/** Asks a grounded question on demand.
 *
 * The answer is written to the shared chat store inside the mutation itself
 * so it survives navigating away while the generation is in flight.
 */
export function useRagAsk() {
  return useMutation({
    mutationFn: async ({ query, topK }: { query: string; topK?: number }) => {
      const result = await ragAsk(query, topK);
      useChatStore.getState().setAssistantResult(result);
      return result;
    },
  });
}

/**
 * Ask a grounded question and render the answer as it arrives.
 *
 * Sources are shown as soon as the first frame lands — before any prose —
 * because a reader should be able to see what an answer is grounded in while
 * it is still being written.
 *
 * The completed answer is committed to the shared chat store the same way the
 * non-streaming hook does, so navigating away mid-generation and coming back
 * still shows the result.
 */
export function useRagAskStream() {
  const [answer, setAnswer] = useState("");
  const [sources, setSources] = useState<RagMatch[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const stop = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
    setIsStreaming(false);
  }, []);

  const ask = useCallback(async (query: string, topK?: number) => {
    // A second question supersedes the first rather than interleaving with it.
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setAnswer("");
    setSources([]);
    setError(null);
    setIsStreaming(true);

    let text = "";
    let matches: RagMatch[] = [];
    let grounded = false;
    let model: string | null = null;

    try {
      for await (const frame of ragAskStream(query, topK, controller.signal)) {
        switch (frame.event) {
          case "sources":
            matches = frame.data;
            setSources(matches);
            break;
          case "delta":
            text += frame.data;
            setAnswer(text);
            break;
          case "error":
            setError(frame.data);
            break;
          case "done":
            grounded = frame.data.grounded;
            model = frame.data.model;
            break;
        }
      }

      useChatStore.getState().setAssistantResult({
        query,
        answer: text,
        grounded,
        model,
        sources: matches,
      });
    } catch (caught) {
      // An abort is the user asking something else, not a failure.
      if ((caught as Error)?.name !== "AbortError") {
        setError("The assistant is unavailable. Please try again.");
      }
    } finally {
      if (abortRef.current === controller) abortRef.current = null;
      setIsStreaming(false);
    }
  }, []);

  return { ask, stop, answer, sources, isStreaming, error };
}
