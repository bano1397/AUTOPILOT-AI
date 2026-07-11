import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { listNotifications, markAllRead, markRead, unreadCount } from "./api";

const NOTIFICATIONS_KEY = ["notifications"];

export function useNotifications(page: number, pageSize = 8) {
  return useQuery({
    queryKey: [...NOTIFICATIONS_KEY, "list", page, pageSize],
    queryFn: () => listNotifications(page, pageSize),
  });
}

/** Unread badge count; refreshed every 30s so alerts appear without a reload. */
export function useUnreadCount() {
  return useQuery({
    queryKey: [...NOTIFICATIONS_KEY, "unread"],
    queryFn: unreadCount,
    refetchInterval: 30_000,
  });
}

export function useMarkRead() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => markRead(id),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: NOTIFICATIONS_KEY }),
  });
}

export function useMarkAllRead() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => markAllRead(),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: NOTIFICATIONS_KEY }),
  });
}
