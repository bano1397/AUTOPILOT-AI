import { useQuery } from "@tanstack/react-query";

import { getAnalyticsOverview } from "./api";

export function useAnalyticsOverview(days: number) {
  return useQuery({
    queryKey: ["analytics", "overview", days],
    queryFn: () => getAnalyticsOverview(days),
  });
}
