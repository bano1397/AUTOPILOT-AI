import { apiFetch } from "@/lib/api/client";

import type { AnalyticsOverview } from "./types";

export function getAnalyticsOverview(days: number): Promise<AnalyticsOverview> {
  return apiFetch<AnalyticsOverview>(`/api/v1/analytics/overview?days=${days}`);
}
