"use client";

import { motion } from "framer-motion";
import { Sparkles } from "lucide-react";

const SUGGESTIONS = [
  "Summarize my uploaded documents",
  "Research the latest trends in our industry",
  "Draft a project plan for a product launch",
  "What does our policy say about remote work?",
];

/** Shown when a conversation has no messages yet. */
export function ChatEmptyState({
  onPick,
}: {
  onPick: (prompt: string) => void;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className="mx-auto flex max-w-xl flex-col items-center justify-center py-14 text-center"
    >
      <div className="flex size-14 items-center justify-center rounded-2xl bg-gradient-to-br from-indigo-500 to-violet-600 text-white shadow-lg">
        <Sparkles className="size-7" />
      </div>
      <h2 className="mt-4 text-xl font-semibold tracking-tight">
        How can the AI team help?
      </h2>
      <p className="mt-1 text-sm text-muted-foreground">
        Ask anything — the supervisor routes your message to the right
        specialist and cites its sources.
      </p>
      <div className="mt-6 grid w-full gap-2 sm:grid-cols-2">
        {SUGGESTIONS.map((suggestion) => (
          <button
            key={suggestion}
            type="button"
            onClick={() => onPick(suggestion)}
            className="rounded-xl border bg-card px-4 py-3 text-left text-sm text-muted-foreground transition-colors hover:border-primary/40 hover:text-foreground"
          >
            {suggestion}
          </button>
        ))}
      </div>
    </motion.div>
  );
}
