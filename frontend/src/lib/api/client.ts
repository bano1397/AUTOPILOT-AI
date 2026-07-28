import { ApiError, type PageMeta } from "@/lib/api/types";
import { API_URL } from "@/lib/config";

interface RequestOptions {
  method?: "GET" | "POST" | "PATCH" | "PUT" | "DELETE";
  /** JSON-serializable payload, or FormData for multipart uploads. */
  body?: unknown;
}

async function request<T>(
  path: string,
  options: RequestOptions,
): Promise<{ data: T; meta: PageMeta | null }> {
  const { method = "GET", body } = options;

  const isForm = typeof FormData !== "undefined" && body instanceof FormData;
  const headers: Record<string, string> = {};
  // FormData sets its own multipart boundary; never override it.
  if (!isForm && body !== undefined)
    headers["Content-Type"] = "application/json";

  const res = await fetch(`${API_URL}${path}`, {
    method,
    headers,
    body: isForm
      ? (body as FormData)
      : body === undefined
        ? undefined
        : JSON.stringify(body),
  });
  const json = await res.json().catch(() => null);

  if (!res.ok || !json || json.success === false) {
    const error = json?.error;
    throw new ApiError(
      error?.message ?? res.statusText ?? "Request failed",
      error?.code ?? "REQUEST_FAILED",
      res.status,
      error?.details,
    );
  }

  return { data: json.data as T, meta: (json.meta ?? null) as PageMeta | null };
}

/**
 * Perform an API request, unwrapping the standard envelope.
 *
 * There is no authentication (see `docs/COMPLETION_PLAN.md` §3), so there are no
 * tokens to attach and no 401-refresh-retry cycle: every request goes out plain.
 */
export async function apiFetch<T>(
  path: string,
  options: RequestOptions = {},
): Promise<T> {
  return (await request<T>(path, options)).data;
}

/** Like {@link apiFetch}, but also returns the envelope's pagination meta. */
export async function apiFetchWithMeta<T>(
  path: string,
  options: RequestOptions = {},
): Promise<{ data: T; meta: PageMeta | null }> {
  return request<T>(path, options);
}
