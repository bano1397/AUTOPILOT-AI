"use client";

import { motion } from "framer-motion";
import { ArrowUp, Sparkles } from "lucide-react";
import { useRouter } from "next/navigation";
import { type FormEvent, useState } from "react";

import { Card } from "@/components/ui/card";
import { useAgentAsk } from "@/features/agents/hooks";
import { useChatStore } from "@/lib/chat/store";

const SUGGESTIONS = [
  "Summarize my uploaded documents",
  "Research our top competitors",
  "Plan a product launch",
  "What does our policy say about remote work?",
];

export function AssistantLauncher() {
  const router = useRouter();
  const [input, setInput] = useState("");
  const addTurn = useChatStore((state) => state.addAgentTurn);
  const conversationId = useChatStore((state) => state.conversationId);
  const ask = useAgentAsk();

  function send(message: string) {
    const trimmed = message.trim();
    if (!trimmed) return;
    // Fire through the shared hook/store, then hand off to the Agents page,
    // where the transcript (and streaming state) is already rendered.
    addTurn({ role: "user", content: trimmed });
    ask.mutate({ message: trimmed, conversationId });
    router.push("/agents");
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    send(input);
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, delay: 0.1 }}
    >
      <Card className="relative overflow-hidden border-primary/20 bg-gradient-to-br from-primary/5 via-transparent to-violet-500/5 p-6">
        <div className="mb-4 flex items-center gap-2">
          <div className="flex size-9 items-center justify-center rounded-xl bg-gradient-to-br from-indigo-500 to-violet-600 text-white shadow-sm">
            <Sparkles className="size-5" />
          </div>
          <div>
            <h2 className="text-lg font-semibold tracking-tight">
              What would you like to automate today?
            </h2>
            <p className="text-sm text-muted-foreground">
              Ask the AI team — it routes your request to the right specialist.
            </p>
          </div>
        </div>

        <form onSubmit={handleSubmit} className="relative">
          <input
            value={input}
            onChange={(event) => setInput(event.target.value)}
            placeholder="Message the AI team…"
            maxLength={4000}
            className="h-12 w-full rounded-xl border border-input bg-background pl-4 pr-12 text-sm shadow-sm outline-none ring-offset-background focus-visible:ring-2 focus-visible:ring-ring"
          />
          <button
            type="submit"
            disabled={!input.trim()}
            aria-label="Send"
            className="absolute right-2 top-2 flex size-8 items-center justify-center rounded-lg bg-primary text-primary-foreground transition-opacity disabled:opacity-40"
          >
            <ArrowUp className="size-4" />
          </button>
        </form>

        <div className="mt-3 flex flex-wrap gap-2">
          {SUGGESTIONS.map((suggestion) => (
            <button
              key={suggestion}
              type="button"
              onClick={() => send(suggestion)}
              className="rounded-full border bg-background/60 px-3 py-1 text-xs text-muted-foreground transition-colors hover:border-primary/40 hover:text-foreground"
            >
              {suggestion}
            </button>
          ))}
        </div>
      </Card>
    </motion.div>
  );
}
