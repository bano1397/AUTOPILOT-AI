import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { getPreferences, updatePreferences } from "./api";
import type { Preferences, PreferencesUpdate } from "./types";

export const PREFERENCES_KEY = ["preferences"] as const;

export function usePreferences() {
  return useQuery({ queryKey: PREFERENCES_KEY, queryFn: getPreferences });
}

/**
 * Persists a partial change. The server returns the full record, so the cache is
 * seeded from the response rather than invalidated — the UI never shows a stale
 * value between the write and a refetch.
 */
export function useUpdatePreferences() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (patch: PreferencesUpdate) => updatePreferences(patch),
    onSuccess: (preferences: Preferences) => {
      queryClient.setQueryData(PREFERENCES_KEY, preferences);
    },
  });
}
