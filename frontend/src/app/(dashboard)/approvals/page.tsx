"use client";

import { ClipboardCheck, ShieldCheck } from "lucide-react";
import { useState } from "react";

import { ApprovalCard } from "@/components/approvals/approval-card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { usePendingApprovals } from "@/features/approvals/hooks";

export default function ApprovalsPage() {
  const [page, setPage] = useState(1);
  const approvals = usePendingApprovals(page);

  const items = approvals.data?.data ?? [];
  const meta = approvals.data?.meta;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="flex items-center gap-2 text-2xl font-semibold tracking-tight">
            <ClipboardCheck className="size-6 text-primary" />
            Approval Center
          </h1>
          <p className="text-muted-foreground">
            Drafts paused for your review — approve to deliver, reject to
            discard.
          </p>
        </div>
        {meta && (
          <div className="flex items-center gap-2 rounded-full border bg-card px-3 py-1.5 text-sm">
            <span className="flex size-2 rounded-full bg-amber-500" />
            <span className="font-medium tabular-nums">{meta.total}</span>
            <span className="text-muted-foreground">pending</span>
          </div>
        )}
      </div>

      {approvals.isPending ? (
        <div className="space-y-4 lg:max-w-3xl">
          <Skeleton className="h-56 rounded-2xl" />
          <Skeleton className="h-56 rounded-2xl" />
        </div>
      ) : items.length === 0 ? (
        <div className="flex flex-col items-center justify-center gap-3 rounded-2xl border py-20 text-center">
          <div className="flex size-14 items-center justify-center rounded-2xl bg-emerald-500/10 text-emerald-500">
            <ShieldCheck className="size-7" />
          </div>
          <div>
            <p className="font-medium">You’re all caught up</p>
            <p className="mx-auto mt-1 max-w-md text-sm text-muted-foreground">
              Nothing awaiting review. In the Agents chat, toggle{" "}
              <span className="font-medium">Require approval</span> and drafts
              will be routed here before delivery.
            </p>
          </div>
        </div>
      ) : (
        <div className="grid gap-4 lg:max-w-3xl">
          {items.map((approval, index) => (
            <ApprovalCard key={approval.id} approval={approval} index={index} />
          ))}
        </div>
      )}

      {meta && meta.pages > 1 && (
        <div className="flex items-center justify-end gap-2 text-sm lg:max-w-3xl">
          <span className="text-muted-foreground">
            Page {meta.page} of {meta.pages}
          </span>
          <Button
            variant="outline"
            size="sm"
            disabled={page <= 1}
            onClick={() => setPage((c) => c - 1)}
          >
            Previous
          </Button>
          <Button
            variant="outline"
            size="sm"
            disabled={page >= meta.pages}
            onClick={() => setPage((c) => c + 1)}
          >
            Next
          </Button>
        </div>
      )}
    </div>
  );
}
