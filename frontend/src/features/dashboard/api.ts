import { apiFetch } from "@/lib/api/client";

import type { DashboardData } from "./types";

export function getDashboard(days = 30): Promise<DashboardData> {
  return apiFetch<DashboardData>(`/api/v1/dashboard?days=${days}`);
}
