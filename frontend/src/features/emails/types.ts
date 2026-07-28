export type EmailIntent =
  | "question"
  | "request"
  | "complaint"
  | "meeting"
  | "invoice"
  | "sales"
  | "support"
  | "spam"
  | "other";

export type EmailStatus =
  | "received"
  | "processing"
  | "awaiting_approval"
  | "sent"
  | "discarded"
  | "failed";

export interface Email {
  id: string;
  sender: string;
  subject: string;
  body: string;
  received_at: string | null;
  intent: EmailIntent | null;
  /** Extracted entity lists, keyed by kind (people, amounts, order_ids, …). */
  entities: Record<string, string[]>;
  status: EmailStatus;
  draft: string | null;
  grounded: boolean | null;
  error: string | null;
  sent_at: string | null;
  created_at: string;
}

export interface SyncSummary {
  fetched: number;
  triaged: number;
  skipped: number;
  failed: number;
}
