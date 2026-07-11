"use client";

import { motion } from "framer-motion";
import { Bot, Check, Clock, Loader2, X } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { Markdown } from "@/components/chat/markdown";
import { SourcesList } from "@/components/common/sources-list";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useDecideApproval } from "@/features/approvals/hooks";
import type { Approval } from "@/features/approvals/types";
import { ApiError } from "@/lib/api/types";
import { formatDate } from "@/lib/utils";

export function ApprovalCard({
  approval,
  index = 0,
}: {
  approval: Approval;
  index?: number;
}) {
  const decide = useDecideApproval();
  const [error, setError] = useState<string | null>(null);
  const payload = approval.payload ?? {};

  function handle(decision: "approved" | "rejected") {
    setError(null);
    decide.mutate(
      { id: approval.id, decision },
      {
        onSuccess: () =>
          toast.success(
            decision === "approved" ? "Answer approved" : "Draft rejected",
          ),
        onError: (err) =>
          setError(err instanceof ApiError ? err.message : "Decision failed."),
      },
    );
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2, delay: Math.min(index * 0.05, 0.3) }}
      className="overflow-hidden rounded-2xl border bg-card"
    >
      {/* Header */}
      <div className="flex flex-wrap items-center gap-2 border-b bg-amber-500/5 px-5 py-3">
        <span className="flex size-8 items-center justify-center rounded-lg bg-amber-500/15 text-amber-600 dark:text-amber-400">
          <Clock className="size-4" />
        </span>
        <div className="mr-auto">
          <p className="text-sm font-semibold">
            Drafted answer awaiting review
          </p>
          <p className="text-xs text-muted-foreground">
            Requested {formatDate(approval.created_at)}
          </p>
        </div>
        {payload.agent && (
          <Badge variant="secondary" className="capitalize">
            <Bot className="mr-1 size-3" />
            {payload.agent}
          </Badge>
        )}
        {payload.grounded ? (
          <Badge variant="success">Grounded</Badge>
        ) : (
          <Badge variant="outline">Ungrounded</Badge>
        )}
        {payload.model && <Badge variant="outline">{payload.model}</Badge>}
      </div>

      {/* Body */}
      <div className="space-y-3 p-5">
        {payload.message && (
          <div>
            <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              Question
            </p>
            <p className="mt-1 text-sm">{payload.message}</p>
          </div>
        )}
        <div>
          <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            Draft answer
          </p>
          <div className="mt-1 rounded-lg border bg-muted/40 p-3">
            {payload.draft_answer ? (
              <Markdown content={payload.draft_answer} />
            ) : (
              <p className="text-sm text-muted-foreground">
                (no draft content)
              </p>
            )}
          </div>
        </div>
        {payload.sources && payload.sources.length > 0 && (
          <SourcesList sources={payload.sources} />
        )}
        {error && <p className="text-sm text-destructive">{error}</p>}
      </div>

      {/* Actions */}
      <div className="flex gap-2 border-t px-5 py-3">
        <Button
          size="sm"
          disabled={decide.isPending}
          onClick={() => handle("approved")}
        >
          {decide.isPending ? (
            <Loader2 className="size-4 animate-spin" />
          ) : (
            <Check className="size-4" />
          )}
          Approve &amp; deliver
        </Button>
        <Button
          size="sm"
          variant="outline"
          disabled={decide.isPending}
          onClick={() => handle("rejected")}
        >
          <X className="size-4" />
          Reject
        </Button>
      </div>
    </motion.div>
  );
}
