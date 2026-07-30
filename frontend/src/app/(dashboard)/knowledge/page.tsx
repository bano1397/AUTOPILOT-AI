"use client";

import { motion } from "framer-motion";
import {
  BookOpen,
  FileText,
  Layers,
  Loader2,
  Search,
  Sparkles,
} from "lucide-react";
import { type FormEvent, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { useAnalyticsOverview } from "@/features/analytics/hooks";
import { fileMeta } from "@/features/documents/file-meta";
import { useRagQuery } from "@/features/rag/hooks";
import type { RagMatch } from "@/features/rag/types";
import { ApiError } from "@/lib/api/types";
import { cn } from "@/lib/utils";

const EXAMPLES = [
  "vacation policy",
  "security requirements",
  "onboarding steps",
  "pricing tiers",
];

/** Heuristic relevance from a vector distance (smaller = closer). Null for
 *  keyword-only hits, which never had a distance. */
function relevance(distance: number | null): number | null {
  if (distance === null) return null;
  return Math.max(0, Math.min(1, 1 - distance));
}

const RETRIEVAL_LABEL: Record<string, string> = {
  vector: "semantic",
  keyword: "keyword",
  hybrid: "both",
};

export default function KnowledgePage() {
  const [query, setQuery] = useState("");
  const search = useRagQuery();
  const overview = useAnalyticsOverview(30);
  const indexed = overview.data?.entities.documents_indexed ?? 0;

  function runSearch(value: string) {
    const trimmed = value.trim();
    if (trimmed && !search.isPending)
      search.mutate({ query: trimmed, topK: 8 });
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    runSearch(query);
  }

  const result = search.data;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="flex items-center gap-2 text-2xl font-semibold tracking-tight">
          <BookOpen className="size-6 text-primary" />
          Knowledge Base
        </h1>
        <p className="text-muted-foreground">
          Semantic search across everything you’ve indexed — ranked by vector
          similarity.
        </p>
      </div>

      {/* Stats */}
      <div className="grid gap-3 sm:grid-cols-3">
        <StatTile
          icon={FileText}
          label="Indexed documents"
          value={indexed.toLocaleString()}
          tint="text-indigo-500 bg-indigo-500/10"
        />
        <StatTile
          icon={Layers}
          label="Embedding model"
          value="nomic-embed-text"
          tint="text-violet-500 bg-violet-500/10"
        />
        <StatTile
          icon={Sparkles}
          label="Search"
          value="Semantic (vector)"
          tint="text-cyan-500 bg-cyan-500/10"
        />
      </div>

      {/* Search */}
      <form onSubmit={handleSubmit}>
        <div className="relative">
          <Search className="pointer-events-none absolute left-4 top-1/2 size-5 -translate-y-1/2 text-muted-foreground" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search your knowledge base…"
            maxLength={2000}
            className="h-12 w-full rounded-xl border bg-card pl-11 pr-28 text-sm shadow-sm outline-none focus-visible:border-primary/40 focus-visible:ring-2 focus-visible:ring-primary/10"
          />
          <button
            type="submit"
            disabled={search.isPending || !query.trim()}
            className="absolute right-2 top-2 flex h-8 items-center gap-1.5 rounded-lg bg-primary px-3 text-sm font-medium text-primary-foreground transition-opacity disabled:opacity-40"
          >
            {search.isPending ? (
              <Loader2 className="size-4 animate-spin" />
            ) : (
              <Search className="size-4" />
            )}
            Search
          </button>
        </div>
        <div className="mt-2 flex flex-wrap gap-2">
          {EXAMPLES.map((example) => (
            <button
              key={example}
              type="button"
              onClick={() => {
                setQuery(example);
                runSearch(example);
              }}
              className="rounded-full border bg-card px-3 py-1 text-xs text-muted-foreground transition-colors hover:border-primary/40 hover:text-foreground"
            >
              {example}
            </button>
          ))}
        </div>
      </form>

      {/* Results */}
      {search.isError && (
        <p className="text-sm text-destructive">
          {search.error instanceof ApiError
            ? search.error.message
            : "Search failed."}
        </p>
      )}

      {result && result.matches.length === 0 && (
        <div className="rounded-xl border py-16 text-center text-sm text-muted-foreground">
          No matches for “{result.query}”. Try different phrasing, or index more
          documents first.
        </div>
      )}

      {result && result.matches.length > 0 && (
        <div className="space-y-3">
          <p className="text-sm text-muted-foreground">
            {result.matches.length} result
            {result.matches.length === 1 ? "" : "s"} for “{result.query}”
          </p>
          {result.matches.map((match, index) => (
            <MatchCard
              key={`${match.document_id}-${match.chunk_index}`}
              match={match}
              index={index}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function StatTile({
  icon: Icon,
  label,
  value,
  tint,
}: {
  icon: typeof BookOpen;
  label: string;
  value: string;
  tint: string;
}) {
  return (
    <div className="flex items-center gap-3 rounded-xl border bg-card p-4">
      <div
        className={cn(
          "flex size-10 items-center justify-center rounded-lg",
          tint,
        )}
      >
        <Icon className="size-5" />
      </div>
      <div className="min-w-0">
        <p className="truncate text-sm font-semibold tracking-tight">{value}</p>
        <p className="text-xs text-muted-foreground">{label}</p>
      </div>
    </div>
  );
}

function MatchCard({ match, index }: { match: RagMatch; index: number }) {
  const { icon: Icon, tint } = fileMeta(match.filename);
  const similarity = relevance(match.distance);
  const score = similarity === null ? null : Math.round(similarity * 100);

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2, delay: Math.min(index * 0.04, 0.3) }}
      className="rounded-xl border bg-card p-4"
    >
      <div className="flex items-center justify-between gap-3">
        <div className="flex min-w-0 items-center gap-2.5">
          <span
            className={cn(
              "flex size-8 shrink-0 items-center justify-center rounded-lg",
              tint,
            )}
          >
            <Icon className="size-4" />
          </span>
          <div className="min-w-0">
            <p className="truncate text-sm font-medium">{match.filename}</p>
            <p className="text-xs text-muted-foreground">
              Chunk #{match.chunk_index + 1}
            </p>
          </div>
        </div>
        <div className="flex shrink-0 flex-col items-end gap-1">
          <div className="flex items-center gap-1.5">
            <Badge variant="secondary" title="how this chunk was retrieved">
              {RETRIEVAL_LABEL[match.retrieval] ?? match.retrieval}
            </Badge>
            <Badge
              variant="outline"
              title={
                match.distance === null
                  ? "found by keyword search; no vector distance"
                  : `vector distance ${match.distance.toFixed(4)}`
              }
            >
              {score === null ? "keyword hit" : `${score}% match`}
            </Badge>
          </div>
          {score !== null && (
            <div className="h-1.5 w-20 overflow-hidden rounded-full bg-muted">
              <div
                className="h-full rounded-full bg-gradient-to-r from-indigo-500 to-violet-500"
                style={{ width: `${score}%` }}
              />
            </div>
          )}
        </div>
      </div>
      <p className="mt-3 border-t pt-3 text-sm leading-relaxed text-muted-foreground">
        {match.text}
      </p>
    </motion.div>
  );
}
