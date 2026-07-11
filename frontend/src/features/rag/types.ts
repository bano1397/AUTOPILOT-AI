export interface RagMatch {
  document_id: string;
  filename: string;
  chunk_index: number;
  text: string;
  distance: number;
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
