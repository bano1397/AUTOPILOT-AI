import { ApiError, type PageMeta } from "@/lib/api/types";
import { useAuthStore } from "@/lib/auth/store";
import { API_URL } from "@/lib/config";

interface RequestOptions {
  method?: "GET" | "POST" | "PATCH" | "PUT" | "DELETE";
  /** JSON-serializable payload, or FormData for multipart uploads. */
  body?: unknown;
  /** Attach the bearer access token (default true). */
  auth?: boolean;
}

// Single-flight refresh: concurrent 401s share one refresh request.
let refreshPromise: Promise<boolean> | null = null;

async function tryRefresh(): Promise<boolean> {
  if (!refreshPromise) {
    refreshPromise = (async () => {
      try {
        // The refresh token travels only in the httpOnly cookie.
        const res = await fetch(`${API_URL}/api/v1/auth/refresh`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          credentials: "include",
          body: "{}",
        });
        const json = await res.json().catch(() => null);
        if (!res.ok || !json?.success) {
          useAuthStore.getState().clear();
          return false;
        }
        useAuthStore.getState().setAccessToken(json.data.access_token);
        return true;
      } catch {
        useAuthStore.getState().clear();
        return false;
      } finally {
        refreshPromise = null;
      }
    })();
  }
  return refreshPromise;
}

async function request<T>(
  path: string,
  options: RequestOptions,
  retry: boolean,
): Promise<{ data: T; meta: PageMeta | null }> {
  const { method = "GET", body, auth = true } = options;

  const isForm = typeof FormData !== "undefined" && body instanceof FormData;
  const headers: Record<string, string> = {};
  // FormData sets its own multipart boundary; never override it.
  if (!isForm && body !== undefined)
    headers["Content-Type"] = "application/json";
  if (auth) {
    const token = useAuthStore.getState().accessToken;
    if (token) headers.Authorization = `Bearer ${token}`;
  }

  const res = await fetch(`${API_URL}${path}`, {
    method,
    headers,
    // Send the auth cookie (scoped to /api/v1/auth server-side).
    credentials: "include",
    body: isForm
      ? (body as FormData)
      : body === undefined
        ? undefined
        : JSON.stringify(body),
  });
  const json = await res.json().catch(() => null);

  if (res.status === 401 && auth && !retry && (await tryRefresh())) {
    return request<T>(path, options, true);
  }

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
 * On a 401 the client attempts a single token refresh and retries once.
 */
export async function apiFetch<T>(
  path: string,
  options: RequestOptions = {},
): Promise<T> {
  return (await request<T>(path, options, false)).data;
}

/** Like {@link apiFetch}, but also returns the envelope's pagination meta. */
export async function apiFetchWithMeta<T>(
  path: string,
  options: RequestOptions = {},
): Promise<{ data: T; meta: PageMeta | null }> {
  return request<T>(path, options, false);
}
