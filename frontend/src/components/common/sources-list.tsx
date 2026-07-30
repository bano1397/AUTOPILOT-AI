"use client";

import { ChevronDown, ChevronRight } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import type { RagMatch } from "@/features/rag/types";

/** Collapsible list of citation cards, numbered to match [n] in answers. */
export function SourcesList({ sources }: { sources: RagMatch[] }) {
  const [open, setOpen] = useState(false);

  if (sources.length === 0) return null;

  return (
    <div className="space-y-3">
      <Button
        variant="ghost"
        size="sm"
        onClick={() => setOpen((current) => !current)}
        className="-ml-2 text-muted-foreground"
      >
        {open ? <ChevronDown /> : <ChevronRight />}
        {sources.length} source{sources.length === 1 ? "" : "s"}
      </Button>
      {open && (
        <div className="space-y-3">
          {sources.map((source, index) => (
            <Card key={`${source.document_id}-${source.chunk_index}`}>
              <CardHeader className="pb-3">
                <div className="flex items-center justify-between gap-2">
                  <CardTitle className="text-sm">
                    [{index + 1}] {source.filename}
                  </CardTitle>
                  <Badge variant="outline">
                    {source.distance === null
                      ? "keyword hit"
                      : `distance ${source.distance.toFixed(3)}`}
                  </Badge>
                </div>
                <CardDescription>
                  Chunk #{source.chunk_index + 1}
                </CardDescription>
              </CardHeader>
              <CardContent className="text-sm leading-relaxed text-muted-foreground">
                {source.text}
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
