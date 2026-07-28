import { apiFetch } from "@/lib/api/client";

import type { Preferences, PreferencesUpdate } from "./types";

export function getPreferences(): Promise<Preferences> {
  return apiFetch<Preferences>("/api/v1/preferences");
}

export function updatePreferences(
  patch: PreferencesUpdate,
): Promise<Preferences> {
  return apiFetch<Preferences>("/api/v1/preferences", {
    method: "PATCH",
    body: patch,
  });
}
