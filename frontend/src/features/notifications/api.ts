import { apiFetch, apiFetchWithMeta } from "@/lib/api/client";
import type { PageMeta } from "@/lib/api/types";

import type { NotificationItem } from "./types";

export function listNotifications(
  page: number,
  pageSize: number,
): Promise<{ data: NotificationItem[]; meta: PageMeta | null }> {
  return apiFetchWithMeta<NotificationItem[]>(
    `/api/v1/notifications?page=${page}&page_size=${pageSize}`,
  );
}

export function unreadCount(): Promise<{ count: number }> {
  return apiFetch<{ count: number }>("/api/v1/notifications/unread-count");
}

export function markRead(id: string): Promise<NotificationItem> {
  return apiFetch<NotificationItem>(`/api/v1/notifications/${id}/read`, {
    method: "POST",
  });
}

export function markAllRead(): Promise<{ updated: number }> {
  return apiFetch<{ updated: number }>("/api/v1/notifications/read-all", {
    method: "POST",
  });
}
