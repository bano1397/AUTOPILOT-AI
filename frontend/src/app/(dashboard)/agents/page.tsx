"use client";

import { Bot } from "lucide-react";
import { type FormEvent, useEffect, useRef, useState } from "react";

import { ChatComposer } from "@/components/chat/chat-composer";
import { ChatEmptyState } from "@/components/chat/chat-empty-state";
import { ChatMessage } from "@/components/chat/chat-message";
import { ConversationHistory } from "@/components/chat/conversation-history";
import { ThinkingIndicator } from "@/components/chat/thinking-indicator";
import { useAgentAsk, useAgents } from "@/features/agents/hooks";
import type { ChatTurn } from "@/features/agents/types";
import { getConversation } from "@/features/conversations/api";
import type { Message } from "@/features/conversations/types";
import { ApiError } from "@/lib/api/types";
import { useChatStore } from "@/lib/chat/store";

function toTurn(message: Message): ChatTurn {
  if (message.role === "user") {
    return { role: "user", content: message.content };
  }
  const meta = message.meta ?? {};
  return {
    role: "assistant",
    content: message.content,
    status: "completed",
    agent: meta.agent,
    grounded: meta.grounded,
    model: meta.model,
    sources: meta.sources,
    webSources: meta.web_sources,
  };
}

export default function AgentsPage() {
  const [input, setInput] = useState("");
  const [requireApproval, setRequireApproval] = useState(false);
  const [loadingId, setLoadingId] = useState<string | null>(null);

  const turns = useChatStore((state) => state.agentTurns);
  const conversationId = useChatStore((state) => state.conversationId);
  const addTurn = useChatStore((state) => state.addAgentTurn);
  const setTurns = useChatStore((state) => state.setAgentTurns);
  const setConversationId = useChatStore((state) => state.setConversationId);
  const resetChat = useChatStore((state) => state.resetAgentChat);

  const ask = useAgentAsk();
  const agents = useAgents();
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [turns, ask.isPending]);

  function send(message: string) {
    const trimmed = message.trim();
    if (!trimmed || ask.isPending) return;
    addTurn({ role: "user", content: trimmed });
    setInput("");
    ask.mutate({ message: trimmed, conversationId, requireApproval });
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    send(input);
  }

  async function loadConversation(id: string) {
    if (id === conversationId || loadingId) return;
    setLoadingId(id);
    try {
      const detail = await getConversation(id);
      setTurns(detail.messages.map(toTurn));
      setConversationId(id);
    } catch {
      // Leave the current transcript untouched on failure.
    } finally {
      setLoadingId(null);
    }
  }

  const agentCount = agents.data?.length ?? 0;

  return (
    <div className="flex h-[calc(100vh-6.5rem)] gap-4">
      {/* History rail */}
      <aside className="hidden w-72 shrink-0 lg:block">
        <ConversationHistory
          activeId={conversationId}
          loadingId={loadingId}
          onSelect={loadConversation}
          onNew={resetChat}
        />
      </aside>

      {/* Chat column */}
      <div className="flex min-w-0 flex-1 flex-col">
        <div className="mb-3 flex items-center justify-between gap-3 border-b pb-3">
          <div>
            <h1 className="flex items-center gap-2 text-lg font-semibold tracking-tight">
              <Bot className="size-5 text-primary" />
              AI Agents
            </h1>
            <p className="text-xs text-muted-foreground">
              {agentCount > 0
                ? `${agentCount} specialists · supervisor auto-routes each message`
                : "Supervisor auto-routes each message to the right specialist"}
            </p>
          </div>
        </div>

        <div className="scrollbar-thin flex-1 space-y-4 overflow-y-auto pb-4 pr-1">
          {turns.length === 0 && !ask.isPending ? (
            <ChatEmptyState onPick={send} />
          ) : (
            turns.map((turn, index) => <ChatMessage key={index} turn={turn} />)
          )}
          {ask.isPending && <ThinkingIndicator />}
          {ask.isError && (
            <p className="text-sm text-destructive">
              {ask.error instanceof ApiError
                ? ask.error.message
                : "The agents are unavailable."}
            </p>
          )}
          <div ref={endRef} />
        </div>

        <form onSubmit={handleSubmit}>
          <ChatComposer
            value={input}
            onChange={setInput}
            onSubmit={() => send(input)}
            pending={ask.isPending}
            footer={
              <label className="flex cursor-pointer items-center gap-2 text-xs text-muted-foreground">
                <input
                  type="checkbox"
                  checked={requireApproval}
                  onChange={(event) => setRequireApproval(event.target.checked)}
                  className="size-3.5 accent-primary"
                />
                Require approval
              </label>
            }
          />
        </form>
      </div>
    </div>
  );
}
