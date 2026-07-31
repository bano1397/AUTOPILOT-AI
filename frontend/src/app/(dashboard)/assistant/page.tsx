"use client";

import { motion } from "framer-motion";
import { FileText, Sparkles } from "lucide-react";
import { useState } from "react";

import { Markdown } from "@/components/chat/markdown";
import { SourcesList } from "@/components/common/sources-list";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { ChatComposer } from "@/components/chat/chat-composer";
import { useRagAskStream } from "@/features/rag/hooks";
import { useChatStore } from "@/lib/chat/store";

const EXAMPLES = [
  "What does our vacation policy say?",
  "Summarize the key points of the latest document",
  "What are the main risks mentioned in our reports?",
];

export default function AssistantPage() {
  const [query, setQuery] = useState("");
  const [asked, setAsked] = useState<string | null>(null);
  const stream = useRagAskStream();
  const stored = useChatStore((state) => state.assistantResult);

  // While streaming, render the partial answer; once finished, fall back to
  // the committed result so navigating away and back still shows it.
  const live = stream.isStreaming || stream.answer.length > 0;
  const result = live
    ? {
        query: asked ?? "",
        answer: stream.answer,
        grounded: stream.sources.length > 0,
        model: null,
        sources: stream.sources,
      }
    : stored;

  function submit(value: string) {
    const trimmed = value.trim();
    if (trimmed && !stream.isStreaming) {
      setAsked(trimmed);
      void stream.ask(trimmed);
      setQuery("");
    }
  }

  return (
    <div className="mx-auto flex h-[calc(100vh-6.5rem)] max-w-3xl flex-col">
      <div className="border-b pb-3">
        <h1 className="flex items-center gap-2 text-lg font-semibold tracking-tight">
          <Sparkles className="size-5 text-primary" />
          Document Assistant
        </h1>
        <p className="text-xs text-muted-foreground">
          Answers grounded in your indexed documents, with citations.
        </p>
      </div>

      <div className="scrollbar-thin flex-1 space-y-4 overflow-y-auto py-4">
        {!result && !stream.isStreaming && (
          <div className="flex flex-col items-center py-12 text-center">
            <div className="flex size-12 items-center justify-center rounded-2xl bg-gradient-to-br from-indigo-500 to-violet-600 text-white shadow-lg">
              <FileText className="size-6" />
            </div>
            <h2 className="mt-4 text-lg font-semibold">Ask your documents</h2>
            <p className="mt-1 text-sm text-muted-foreground">
              Retrieval-augmented answers with inline sources.
            </p>
            <div className="mt-5 flex flex-wrap justify-center gap-2">
              {EXAMPLES.map((example) => (
                <button
                  key={example}
                  type="button"
                  onClick={() => submit(example)}
                  className="rounded-full border bg-card px-3 py-1.5 text-xs text-muted-foreground transition-colors hover:border-primary/40 hover:text-foreground"
                >
                  {example}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Sources arrive before any prose, so citations render while the
            answer is still being written. */}
        {stream.isStreaming && stream.answer.length === 0 && (
          <p className="text-sm text-muted-foreground">
            {stream.sources.length > 0
              ? `Found ${stream.sources.length} source${stream.sources.length === 1 ? "" : "s"} — writing the answer…`
              : "Searching your documents…"}
          </p>
        )}

        {stream.error && (
          <p className="text-sm text-destructive">{stream.error}</p>
        )}

        {result && (
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
          >
            <Card>
              <CardContent className="space-y-4 p-5">
                <div className="flex flex-wrap items-center gap-2">
                  {result.grounded ? (
                    <Badge variant="success">Grounded</Badge>
                  ) : (
                    <Badge variant="warning">No sources found</Badge>
                  )}
                  {result.model && (
                    <Badge variant="outline">{result.model}</Badge>
                  )}
                  {stream.isStreaming && (
                    <Badge variant="secondary">streaming…</Badge>
                  )}
                  <span className="text-xs text-muted-foreground">
                    “{result.query}”
                  </span>
                </div>
                <Markdown content={result.answer} />
                <SourcesList sources={result.sources} />
              </CardContent>
            </Card>
          </motion.div>
        )}
      </div>

      <ChatComposer
        value={query}
        onChange={setQuery}
        onSubmit={() => submit(query)}
        pending={stream.isStreaming}
        placeholder="Ask a question about your documents…"
        maxLength={2000}
      />
    </div>
  );
}
