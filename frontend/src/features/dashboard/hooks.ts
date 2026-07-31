import { useQuery } from "@tanstack/react-query";

import { getDashboard } from "./api";

/**
 * The landing page's single read.
 *
 * Replaces three parallel calls: three round trips before anything rendered,
 * three loading states for one screen, and three snapshots that could land
 * either side of a write and show a dashboard that never existed at any
 * single moment.
 */
export function useDashboard(days = 30) {
  return useQuery({
    queryKey: ["dashboard", days],
    queryFn: () => getDashboard(days),
  });
}
