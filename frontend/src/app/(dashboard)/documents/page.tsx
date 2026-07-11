"use client";

import { DocumentDropzone } from "@/components/documents/document-dropzone";
import { DocumentStats } from "@/components/documents/document-stats";
import { DocumentsView } from "@/components/documents/documents-view";

export default function DocumentsPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Documents</h1>
        <p className="text-muted-foreground">
          Upload company documents — they’re chunked, embedded, and indexed into
          your knowledge base automatically.
        </p>
      </div>

      <DocumentStats />
      <DocumentDropzone />
      <DocumentsView />
    </div>
  );
}
