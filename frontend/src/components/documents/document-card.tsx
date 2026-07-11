"use client";

import { motion } from "framer-motion";
import { MoreVertical, Trash2 } from "lucide-react";
import { toast } from "sonner";

import { StatusBadge } from "@/components/documents/status-badge";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useDeleteDocument } from "@/features/documents/hooks";
import { fileMeta } from "@/features/documents/file-meta";
import type { DocumentItem } from "@/features/documents/types";
import { cn } from "@/lib/utils";
import { formatBytes, formatDate } from "@/lib/utils";

export function DocumentCard({
  document,
  index = 0,
}: {
  document: DocumentItem;
  index?: number;
}) {
  const del = useDeleteDocument();
  const { icon: Icon, tint, ext } = fileMeta(document.filename);

  function confirmDelete() {
    toast(`Delete “${document.filename}”?`, {
      description: "This also removes its indexed vectors.",
      action: {
        label: "Delete",
        onClick: () =>
          del.mutate(document.id, {
            onSuccess: () => toast.success("Document deleted"),
            onError: () => toast.error("Delete failed"),
          }),
      },
    });
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2, delay: Math.min(index * 0.03, 0.3) }}
      className="group flex flex-col rounded-xl border bg-card p-4 transition-shadow hover:shadow-md"
    >
      <div className="flex items-start justify-between">
        <div
          className={cn(
            "flex size-10 items-center justify-center rounded-lg",
            tint,
          )}
        >
          <Icon className="size-5" />
        </div>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <button
              type="button"
              aria-label="Document actions"
              className="rounded-md p-1 text-muted-foreground opacity-0 transition-opacity hover:bg-accent group-hover:opacity-100 data-[state=open]:opacity-100"
            >
              <MoreVertical className="size-4" />
            </button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuItem
              onClick={confirmDelete}
              className="text-rose-600 focus:text-rose-600 dark:text-rose-400 [&_svg]:text-rose-500"
            >
              <Trash2 />
              Delete
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>

      <p
        className="mt-3 truncate text-sm font-medium"
        title={document.filename}
      >
        {document.filename}
      </p>
      <p className="mt-0.5 text-xs uppercase text-muted-foreground">{ext}</p>

      {document.status === "failed" && document.metadata.error && (
        <p className="mt-1 line-clamp-2 text-xs text-destructive">
          {document.metadata.error}
        </p>
      )}

      <div className="mt-3 flex items-center justify-between">
        <StatusBadge status={document.status} />
        <span className="text-xs text-muted-foreground">
          {document.metadata.chunk_count != null
            ? `${document.metadata.chunk_count} chunks`
            : "—"}
        </span>
      </div>

      <div className="mt-3 flex items-center justify-between border-t pt-2 text-xs text-muted-foreground">
        <span>{formatBytes(document.size_bytes)}</span>
        <span>{formatDate(document.created_at)}</span>
      </div>
    </motion.div>
  );
}
