/** Shared API envelope types and the typed error thrown by the client. */

export interface PageMeta {
  page: number;
  page_size: number;
  total: number;
  pages: number;
}

export interface ApiEnvelope<T> {
  success: true;
  data: T;
  meta?: PageMeta | null;
}

export interface ApiErrorEnvelope {
  success: false;
  error: {
    code: string;
    message: string;
    details?: Record<string, unknown>;
  };
}

/** Thrown when the API returns an error envelope or a non-OK status. */
export class ApiError extends Error {
  readonly code: string;
  readonly status: number;
  readonly details?: Record<string, unknown>;

  constructor(
    message: string,
    code: string,
    status: number,
    details?: Record<string, unknown>,
  ) {
    super(message);
    this.name = "ApiError";
    this.code = code;
    this.status = status;
    this.details = details;
  }
}
