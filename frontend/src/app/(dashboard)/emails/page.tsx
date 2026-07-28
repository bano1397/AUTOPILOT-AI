"use client";

import { Loader2, Mail, RefreshCw } from "lucide-react";
import { useState } from "react";

import { EmailCard } from "@/components/emails/email-card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useEmails, useSyncMailbox } from "@/features/emails/hooks";
import type { EmailStatus } from "@/features/emails/types";
import { ApiError } from "@/lib/api/types";
import { cn } from "@/lib/utils";

const FILTERS: { key: EmailStatus | undefined; label: string }[] = [
  { key: undefined, label: "All" },
  { key: "awaiting_approval", label: "Needs review" },
  { key: "sent", label: "Sent" },
  { key: "discarded", label: "Discarded" },
  { key: "failed", label: "Failed" },
];

export default function EmailsPage() {
  const [status, setStatus] = useState<EmailStatus | undefined>(
    "awaiting_approval",
  );
  const emails = useEmails(1, status);
  const sync = useSyncMailbox();

  const syncError =
    sync.error instanceof ApiError ? sync.error.message : null;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Email</h1>
          <p className="text-muted-foreground">
            Incoming mail is classified, grounded in your documents, and drafted
            for you. Replies are only sent when you send them.
          </p>
        </div>
        <Button onClick={() => sync.mutate(undefined)} disabled={sync.isPending}>
          {sync.isPending ? (
            <Loader2 className="size-4 animate-spin" />
          ) : (
            <RefreshCw className="size-4" />
          )}
          Sync mailbox
        </Button>
      </div>

      {sync.data && (
        <p className="rounded-lg border bg-card p-3 text-sm">
          Fetched {sync.data.fetched} · triaged {sync.data.triaged} · skipped{" "}
          {sync.data.skipped}
          {sync.data.failed > 0 && ` · failed ${sync.data.failed}`}
        </p>
      )}
      {syncError && (
        <p role="alert" className="rounded-lg border border-destructive/40 bg-destructive/5 p-3 text-sm text-destructive">
          {syncError}
        </p>
      )}

      <div className="flex flex-wrap items-center gap-1">
        {FILTERS.map((filter) => (
          <button
            key={filter.label}
            type="button"
            onClick={() => setStatus(filter.key)}
            className={cn(
              "rounded-lg px-3 py-1.5 text-sm font-medium transition-colors",
              status === filter.key
                ? "bg-primary/10 text-primary"
                : "text-muted-foreground hover:bg-accent hover:text-foreground",
            )}
          >
            {filter.label}
          </button>
        ))}
      </div>

      {emails.isLoading ? (
        <div className="space-y-3">
          {[0, 1].map((key) => (
            <Skeleton key={key} className="h-40 w-full" />
          ))}
        </div>
      ) : emails.isError ? (
        <p role="alert" className="text-sm text-destructive">
          Could not load email.
        </p>
      ) : emails.data?.data.length ? (
        <div className="space-y-3">
          {emails.data.data.map((email) => (
            <EmailCard key={email.id} email={email} />
          ))}
        </div>
      ) : (
        <div className="rounded-lg border border-dashed p-10 text-center">
          <Mail className="mx-auto size-8 text-muted-foreground" />
          <p className="mt-2 font-medium">Nothing here</p>
          <p className="text-sm text-muted-foreground">
            Sync the mailbox to triage new messages. Configure IMAP_HOST,
            IMAP_USERNAME, and IMAP_PASSWORD to connect one.
          </p>
        </div>
      )}
    </div>
  );
}
