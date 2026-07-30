import { apiFetch, apiFetchWithMeta } from "@/lib/api/client";
import type { PageMeta } from "@/lib/api/types";

import type { DocumentItem, UploadCapabilities } from "./types";

export function uploadDocument(file: File): Promise<DocumentItem> {
  const form = new FormData();
  form.append("file", file);
  return apiFetch<DocumentItem>("/api/v1/documents", {
    method: "POST",
    body: form,
  });
}

export function listDocuments(
  page: number,
  pageSize: number,
): Promise<{ data: DocumentItem[]; meta: PageMeta | null }> {
  return apiFetchWithMeta<DocumentItem[]>(
    `/api/v1/documents?page=${page}&page_size=${pageSize}`,
  );
}

export function deleteDocument(id: string): Promise<unknown> {
  return apiFetch(`/api/v1/documents/${id}`, { method: "DELETE" });
}

export function getUploadCapabilities(): Promise<UploadCapabilities> {
  return apiFetch<UploadCapabilities>("/api/v1/documents/capabilities");
}
