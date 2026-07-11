export type DocumentStatus = "uploaded" | "processing" | "indexed" | "failed";

export interface DocumentItem {
  id: string;
  filename: string;
  mime_type: string;
  size_bytes: number;
  status: DocumentStatus;
  metadata: {
    chunk_count?: number;
    error?: string;
  } & Record<string, unknown>;
  created_at: string;
}
