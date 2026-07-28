import { apiFetch, apiFetchWithMeta } from "@/lib/api/client";
import type { PageMeta } from "@/lib/api/types";

import type { Email, EmailStatus, SyncSummary } from "./types";

export function listEmails(
  page = 1,
  status?: EmailStatus,
  pageSize = 20,
): Promise<{ data: Email[]; meta: PageMeta | null }> {
  const params = new URLSearchParams({
    page: String(page),
    page_size: String(pageSize),
  });
  if (status) params.set("status", status);
  return apiFetchWithMeta<Email[]>(`/api/v1/emails?${params.toString()}`);
}

export function syncMailbox(): Promise<SyncSummary> {
  return apiFetch<SyncSummary>("/api/v1/emails/sync", { method: "POST" });
}

/** Sends the draft. `body` overrides it when the reviewer edited the text. */
export function sendReply(id: string, body?: string): Promise<Email> {
  return apiFetch<Email>(`/api/v1/emails/${id}/send`, {
    method: "POST",
    body: body ? { body } : {},
  });
}

export function discardDraft(id: string): Promise<Email> {
  return apiFetch<Email>(`/api/v1/emails/${id}/discard`, { method: "POST" });
}

export function retriageEmail(id: string): Promise<Email> {
  return apiFetch<Email>(`/api/v1/emails/${id}/retriage`, { method: "POST" });
}
