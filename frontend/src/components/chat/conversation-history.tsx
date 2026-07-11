"use client";

import { Loader2, MessageSquarePlus, MessagesSquare } from "lucide-react";

import { Skeleton } from "@/components/ui/skeleton";
import { useConversations } from "@/features/conversations/hooks";
import { cn } from "@/lib/utils";

function timeAgo(iso: string): string {
  const seconds = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000);
  if (seconds < 60) return "just now";
  const m = Math.floor(seconds / 60);
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}

export function ConversationHistory({
  activeId,
  loadingId,
  onSelect,
  onNew,
}: {
  activeId?: string;
  loadingId?: string | null;
  onSelect: (id: string) => void;
  onNew: () => void;
}) {
  const conversations = useConversations(1);
  const items = conversations.data?.data ?? [];

  return (
    <div className="flex h-full flex-col">
      <button
        type="button"
        onClick={onNew}
        className="mb-3 flex h-9 items-center justify-center gap-2 rounded-lg border bg-card text-sm font-medium transition-colors hover:border-primary/40 hover:text-primary"
      >
        <MessageSquarePlus className="size-4" />
        New chat
      </button>

      <p className="px-1 pb-2 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground/70">
        History
      </p>

      <div className="scrollbar-thin -mr-1 flex-1 space-y-1 overflow-y-auto pr-1">
        {conversations.isLoading ? (
          Array.from({ length: 5 }).map((_, i) => (
            <Skeleton key={i} className="h-12 w-full rounded-lg" />
          ))
        ) : items.length === 0 ? (
          <div className="flex flex-col items-center gap-2 py-10 text-center">
            <MessagesSquare className="size-6 text-muted-foreground/50" />
            <p className="text-xs text-muted-foreground">
              No conversations yet.
            </p>
          </div>
        ) : (
          items.map((conversation) => {
            const active = conversation.id === activeId;
            return (
              <button
                key={conversation.id}
                type="button"
                onClick={() => onSelect(conversation.id)}
                className={cn(
                  "flex w-full flex-col gap-0.5 rounded-lg border px-3 py-2 text-left transition-colors",
                  active
                    ? "border-primary/40 bg-primary/5"
                    : "border-transparent hover:bg-accent",
                )}
              >
                <div className="flex items-center gap-2">
                  <span className="truncate text-sm font-medium">
                    {conversation.title || "Untitled chat"}
                  </span>
                  {loadingId === conversation.id && (
                    <Loader2 className="ml-auto size-3.5 shrink-0 animate-spin text-muted-foreground" />
                  )}
                </div>
                <span className="text-[11px] text-muted-foreground">
                  {timeAgo(conversation.updated_at)}
                </span>
              </button>
            );
          })
        )}
      </div>
    </div>
  );
}
