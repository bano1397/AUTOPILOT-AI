import { useQuery } from "@tanstack/react-query";

import { API_URL } from "@/lib/config";

/**
 * Polls the backend `/health` endpoint so the shell can show a live
 * connection indicator. Unauthenticated and outside the API envelope.
 */
export function useHealth() {
  return useQuery({
    queryKey: ["system", "health"],
    queryFn: async () => {
      const res = await fetch(`${API_URL}/health`, { cache: "no-store" });
      if (!res.ok) throw new Error("Backend unhealthy");
      return (await res.json()) as { status: string };
    },
    refetchInterval: 30_000,
    staleTime: 15_000,
    retry: 1,
  });
}
