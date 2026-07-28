"use client";

import { Loader2, RefreshCw, Send, Trash2 } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  useDiscardDraft,
  useRetriageEmail,
  useSendReply,
} from "@/features/emails/hooks";
import type { Email, EmailStatus } from "@/features/emails/types";
import { formatDate } from "@/lib/utils";

const STATUS_VARIANT: Record<
  EmailStatus,
  "default" | "secondary" | "outline" | "success" | "warning" | "destructive"
> = {
  received: "outline",
  processing: "secondary",
  awaiting_approval: "warning",
  sent: "success",
  discarded: "secondary",
  failed: "destructive",
};

export function EmailCard({ email }: { email: Email }) {
  const [draft, setDraft] = useState(email.draft ?? "");
  const send = useSendReply();
  const discard = useDiscardDraft();
  const retriage = useRetriageEmail();
  const decidable =
    email.status === "awaiting_approval" || email.status === "failed";
  const busy = send.isPending || discard.isPending || retriage.isPending;
  const entities = Object.entries(email.entities).filter(
    ([key]) => key !== "summary",
  );

  return (
    <Card>
      <CardContent className="space-y-3 p-4">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div className="min-w-0">
            <p className="truncate font-medium">{email.subject || "(no subject)"}</p>
            <p className="truncate text-sm text-muted-foreground">
              {email.sender}
              {email.received_at && ` · ${formatDate(email.received_at)}`}
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-1.5">
            {email.intent && (
              <Badge variant="secondary" className="capitalize">
                {email.intent}
              </Badge>
            )}
            <Badge variant={STATUS_VARIANT[email.status]}>
              {email.status.replace(/_/g, " ")}
            </Badge>
            {email.grounded !== null && (
              <Badge variant={email.grounded ? "success" : "outline"}>
                {email.grounded ? "Grounded" : "No sources"}
              </Badge>
            )}
          </div>
        </div>

        {email.entities.summary?.[0] && (
          <p className="text-sm">{email.entities.summary[0]}</p>
        )}

        {entities.length > 0 && (
          <div className="flex flex-wrap gap-1.5 text-xs">
            {entities.map(([kind, values]) => (
              <span key={kind} className="rounded bg-muted px-1.5 py-0.5">
                <span className="text-muted-foreground">{kind}: </span>
                {values.join(", ")}
              </span>
            ))}
          </div>
        )}

        <details className="text-sm">
          <summary className="cursor-pointer text-muted-foreground">
            Original message
          </summary>
          <pre className="mt-2 max-h-48 overflow-auto whitespace-pre-wrap rounded-lg bg-muted p-3 text-xs">
            {email.body}
          </pre>
        </details>

        {email.error && (
          <p role="alert" className="text-sm text-destructive">
            {email.error}
          </p>
        )}

        {decidable && email.draft !== null && (
          <div className="space-y-2 rounded-lg border p-3">
            <p className="text-xs font-medium text-muted-foreground">
              Drafted reply — edit before sending if you like. Nothing is sent
              until you press Send.
            </p>
            <textarea
              aria-label="Drafted reply"
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              rows={6}
              className="w-full rounded-md border bg-background p-2 text-sm"
            />
            <div className="flex flex-wrap gap-2">
              <Button
                size="sm"
                disabled={busy || !draft.trim()}
                onClick={() =>
                  send.mutate({
                    id: email.id,
                    body: draft === email.draft ? undefined : draft,
                  })
                }
              >
                {send.isPending ? (
                  <Loader2 className="size-3.5 animate-spin" />
                ) : (
                  <Send className="size-3.5" />
                )}
                Send reply
              </Button>
              <Button
                size="sm"
                variant="outline"
                disabled={busy}
                onClick={() => discard.mutate(email.id)}
              >
                <Trash2 className="size-3.5" />
                Discard
              </Button>
              <Button
                size="sm"
                variant="ghost"
                disabled={busy}
                onClick={() => retriage.mutate(email.id)}
              >
                <RefreshCw className="size-3.5" />
                Re-draft
              </Button>
            </div>
            {(send.isError || discard.isError || retriage.isError) && (
              <p role="alert" className="text-sm text-destructive">
                That action failed — the draft is unchanged.
              </p>
            )}
          </div>
        )}

        {email.status === "sent" && email.draft && (
          <div className="rounded-lg border border-emerald-500/30 bg-emerald-500/5 p-3">
            <p className="mb-1 text-xs font-medium text-muted-foreground">
              Sent reply
            </p>
            <p className="whitespace-pre-wrap text-sm">{email.draft}</p>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
