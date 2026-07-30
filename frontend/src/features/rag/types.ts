/** Which retriever(s) surfaced a chunk. */
export type RetrievalSource = "vector" | "keyword" | "hybrid";

export interface RagMatch {
  document_id: string;
  filename: string;
  chunk_index: number;
  text: string;
  retrieval: RetrievalSource;
  /** Fused/reranked ordering score. Comparable only within one result set. */
  score: number;
  /** Cosine distance, or null for a keyword-only hit that no vector search
   *  ranked -- showing a number there would be inventing one. */
  distance: number | null;
}

export interface RagQueryResult {
  query: string;
  matches: RagMatch[];
}

export interface RagAskResult {
  query: string;
  answer: string;
  /** False when no relevant documents were found (the LLM was not invoked). */
  grounded: boolean;
  model: string | null;
  sources: RagMatch[];
}
