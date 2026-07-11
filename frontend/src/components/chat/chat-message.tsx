"use client";

import { motion } from "framer-motion";
import { Bot, Check, Copy, Globe } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { Markdown } from "@/components/chat/markdown";
import { SourcesList } from "@/components/common/sources-list";
import { Badge } from "@/components/ui/badge";
import type { ChatTurn } from "@/features/agents/types";
import { cn } from "@/lib/utils";

export function ChatMessage({ turn }: { turn: ChatTurn }) {
  if (turn.role === "user") {
    return (
      <motion.div
        initial={{ opacity: 0, y: 6 }}
        animate={{ opacity: 1, y: 0 }}
        className="flex justify-end"
      >
        <div className="max-w-[80%] whitespace-pre-wrap rounded-2xl rounded-tr-sm bg-primary px-4 py-2.5 text-sm text-primary-foreground">
          {turn.content}
        </div>
      </motion.div>
    );
  }
  return <AssistantMessage turn={turn} />;
}

function AssistantMessage({ turn }: { turn: ChatTurn }) {
  const [copied, setCopied] = useState(false);
  const awaiting = turn.status === "awaiting_approval";

  async function copy() {
    await navigator.clipboard.writeText(turn.content).catch(() => undefined);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      className="flex gap-3"
    >
      <div className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-gradient-to-br from-indigo-500 to-violet-600 text-white">
        <Bot className="size-4" />
      </div>
      <div
        className={cn(
          "group min-w-0 flex-1 space-y-2 rounded-2xl rounded-tl-sm border bg-card px-4 py-3",
          awaiting && "border-amber-500/50",
        )}
      >
        <div className="flex flex-wrap items-center gap-1.5">
          {turn.agent && (
            <Badge variant="secondary" className="capitalize">
              {turn.agent}
            </Badge>
          )}
          {awaiting ? (
            <Badge variant="warning">Awaiting approval</Badge>
          ) : turn.grounded ? (
            <Badge variant="success">Grounded</Badge>
          ) : (
            <Badge variant="outline">Ungrounded</Badge>
          )}
          {turn.model && <Badge variant="outline">{turn.model}</Badge>}
          <button
            type="button"
            onClick={copy}
            aria-label="Copy message"
            className="ml-auto rounded-md p-1 text-muted-foreground opacity-0 transition-opacity hover:text-foreground group-hover:opacity-100"
          >
            {copied ? (
              <Check className="size-3.5 text-emerald-500" />
            ) : (
              <Copy className="size-3.5" />
            )}
          </button>
        </div>

        <Markdown content={turn.content} />

        {awaiting && (
          <p className="text-xs text-muted-foreground">
            This draft is paused for review — decide it on the{" "}
            <Link
              href="/approvals"
              className="font-medium text-primary underline"
            >
              Approvals page
            </Link>
            .
          </p>
        )}

        {turn.sources && turn.sources.length > 0 && (
          <SourcesList sources={turn.sources} />
        )}

        {turn.webSources && turn.webSources.length > 0 && (
          <div className="space-y-1 border-t pt-2">
            <p className="flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
              <Globe className="size-3.5" /> Web sources
            </p>
            {turn.webSources.map((source, index) => (
              <a
                key={source.url}
                href={source.url}
                target="_blank"
                rel="noopener noreferrer"
                className="block truncate text-xs text-muted-foreground underline-offset-2 hover:text-foreground hover:underline"
              >
                [{index + 1}] {source.title || source.url}
              </a>
            ))}
          </div>
        )}
      </div>
    </motion.div>
  );
}
