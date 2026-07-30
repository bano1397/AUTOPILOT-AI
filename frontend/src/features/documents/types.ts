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

/** Upload rules reported by the server (see GET /api/v1/documents/capabilities). */
export interface UploadCapabilities {
  allowed_extensions: string[];
  max_upload_size_mb: number;
  ocr_enabled: boolean;
}
