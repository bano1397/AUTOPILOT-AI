"use client";

import {
  ArrowUpDown,
  FileText,
  LayoutGrid,
  List,
  Loader2,
  Search,
} from "lucide-react";
import { useMemo, useState } from "react";

import { DocumentCard } from "@/components/documents/document-card";
import { StatusBadge } from "@/components/documents/status-badge";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useDocuments } from "@/features/documents/hooks";
import type { DocumentItem, DocumentStatus } from "@/features/documents/types";
import { fileMeta } from "@/features/documents/file-meta";
import { cn, formatBytes, formatDate } from "@/lib/utils";

type SortKey = "recent" | "name" | "size";
const STATUS_FILTERS: Array<{ key: "all" | DocumentStatus; label: string }> = [
  { key: "all", label: "All" },
  { key: "indexed", label: "Indexed" },
  { key: "processing", label: "Processing" },
  { key: "failed", label: "Failed" },
];
const SORT_LABELS: Record<SortKey, string> = {
  recent: "Newest",
  name: "Name",
  size: "Size",
};

export function DocumentsView() {
  const [page, setPage] = useState(1);
  const [view, setView] = useState<"grid" | "list">("grid");
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState<"all" | DocumentStatus>("all");
  const [sort, setSort] = useState<SortKey>("recent");

  const { data, isLoading, isError } = useDocuments(page);
  const documents = useMemo(() => data?.data ?? [], [data]);
  const meta = data?.meta;

  const visible = useMemo(() => {
    let items = [...documents];
    if (status !== "all") items = items.filter((d) => d.status === status);
    if (query.trim()) {
      const q = query.toLowerCase();
      items = items.filter((d) => d.filename.toLowerCase().includes(q));
    }
    items.sort((a, b) => {
      if (sort === "name") return a.filename.localeCompare(b.filename);
      if (sort === "size") return b.size_bytes - a.size_bytes;
      return +new Date(b.created_at) - +new Date(a.created_at);
    });
    return items;
  }, [documents, status, query, sort]);

  return (
    <div className="space-y-4">
      {/* Toolbar */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
        <div className="relative flex-1">
          <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Filter by name…"
            className="h-9 w-full rounded-lg border bg-card pl-9 pr-3 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring"
          />
        </div>

        <div className="flex items-center gap-1 rounded-lg border bg-card p-0.5">
          {STATUS_FILTERS.map((filter) => (
            <button
              key={filter.key}
              type="button"
              onClick={() => setStatus(filter.key)}
              className={cn(
                "rounded-md px-2.5 py-1 text-xs font-medium transition-colors",
                status === filter.key
                  ? "bg-primary text-primary-foreground"
                  : "text-muted-foreground hover:text-foreground",
              )}
            >
              {filter.label}
            </button>
          ))}
        </div>

        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="outline" size="sm">
              <ArrowUpDown className="size-4" />
              {SORT_LABELS[sort]}
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            {(Object.keys(SORT_LABELS) as SortKey[]).map((key) => (
              <DropdownMenuItem key={key} onClick={() => setSort(key)}>
                {SORT_LABELS[key]}
              </DropdownMenuItem>
            ))}
          </DropdownMenuContent>
        </DropdownMenu>

        <div className="flex items-center gap-0.5 rounded-lg border bg-card p-0.5">
          <button
            type="button"
            onClick={() => setView("grid")}
            aria-label="Grid view"
            className={cn(
              "rounded-md p-1.5 transition-colors",
              view === "grid"
                ? "bg-accent text-foreground"
                : "text-muted-foreground hover:text-foreground",
            )}
          >
            <LayoutGrid className="size-4" />
          </button>
          <button
            type="button"
            onClick={() => setView("list")}
            aria-label="List view"
            className={cn(
              "rounded-md p-1.5 transition-colors",
              view === "list"
                ? "bg-accent text-foreground"
                : "text-muted-foreground hover:text-foreground",
            )}
          >
            <List className="size-4" />
          </button>
        </div>
      </div>

      {/* Content */}
      {isLoading ? (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {Array.from({ length: 8 }).map((_, i) => (
            <Skeleton key={i} className="h-40 rounded-xl" />
          ))}
        </div>
      ) : isError ? (
        <div className="rounded-xl border py-16 text-center text-sm text-destructive">
          Failed to load documents.
        </div>
      ) : documents.length === 0 ? (
        <EmptyState />
      ) : visible.length === 0 ? (
        <div className="rounded-xl border py-16 text-center text-sm text-muted-foreground">
          No documents match your filters.
        </div>
      ) : view === "grid" ? (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {visible.map((document, index) => (
            <DocumentCard key={document.id} document={document} index={index} />
          ))}
        </div>
      ) : (
        <ListView documents={visible} />
      )}

      {/* Pagination */}
      {meta && meta.pages > 1 && (
        <div className="flex items-center justify-end gap-2 text-sm">
          <span className="text-muted-foreground">
            Page {meta.page} of {meta.pages} · {meta.total} documents
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

function ListView({ documents }: { documents: DocumentItem[] }) {
  return (
    <div className="overflow-hidden rounded-xl border">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Name</TableHead>
            <TableHead>Status</TableHead>
            <TableHead>Chunks</TableHead>
            <TableHead>Size</TableHead>
            <TableHead>Uploaded</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {documents.map((document) => {
            const { icon: Icon, tint } = fileMeta(document.filename);
            return (
              <TableRow key={document.id}>
                <TableCell className="font-medium">
                  <div className="flex items-center gap-2.5">
                    <span
                      className={cn(
                        "flex size-7 shrink-0 items-center justify-center rounded-md",
                        tint,
                      )}
                    >
                      <Icon className="size-3.5" />
                    </span>
                    <span className="truncate">{document.filename}</span>
                  </div>
                </TableCell>
                <TableCell>
                  <StatusBadge status={document.status} />
                </TableCell>
                <TableCell>{document.metadata.chunk_count ?? "—"}</TableCell>
                <TableCell>{formatBytes(document.size_bytes)}</TableCell>
                <TableCell className="text-muted-foreground">
                  {formatDate(document.created_at)}
                </TableCell>
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
    </div>
  );
}

function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center gap-2 rounded-xl border py-16 text-muted-foreground">
      <FileText className="size-8" />
      <p className="text-sm">
        No documents yet. Upload one to build your knowledge base.
      </p>
    </div>
  );
}

/** Small standalone spinner reused if needed. */
export function DocumentsLoading() {
  return (
    <div className="flex items-center justify-center py-16 text-muted-foreground">
      <Loader2 className="mr-2 animate-spin" /> Loading…
    </div>
  );
}
