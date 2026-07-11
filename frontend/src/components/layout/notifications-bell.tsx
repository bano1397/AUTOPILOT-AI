"use client";

import {
  Bell,
  CheckCheck,
  ClipboardCheck,
  FileText,
  type LucideIcon,
  Mail,
  Workflow,
} from "lucide-react";
import { useState } from "react";

import {
  useMarkAllRead,
  useMarkRead,
  useNotifications,
  useUnreadCount,
} from "@/features/notifications/hooks";
import type { NotificationItem } from "@/features/notifications/types";
import { cn, formatDate } from "@/lib/utils";

function iconFor(type: string): { icon: LucideIcon; tint: string } {
  const t = type.toLowerCase();
  if (t.includes("approval"))
    return { icon: ClipboardCheck, tint: "text-amber-500 bg-amber-500/10" };
  if (t.includes("workflow") || t.includes("run"))
    return { icon: Workflow, tint: "text-indigo-500 bg-indigo-500/10" };
  if (t.includes("document") || t.includes("index"))
    return { icon: FileText, tint: "text-cyan-500 bg-cyan-500/10" };
  if (t.includes("digest") || t.includes("email"))
    return { icon: Mail, tint: "text-violet-500 bg-violet-500/10" };
  return { icon: Bell, tint: "text-slate-500 bg-slate-500/10" };
}

export function NotificationsBell() {
  const [open, setOpen] = useState(false);
  const [unreadOnly, setUnreadOnly] = useState(false);
  const unread = useUnreadCount();
  const notifications = useNotifications(1);
  const markRead = useMarkRead();
  const markAll = useMarkAllRead();

  const count = unread.data?.count ?? 0;
  const all = notifications.data?.data ?? [];
  const items = unreadOnly ? all.filter((n) => !n.read) : all;

  return (
    <div className="relative">
      <button
        type="button"
        aria-label={`Notifications (${count} unread)`}
        onClick={() => setOpen((c) => !c)}
        className="relative flex size-9 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
      >
        <Bell className="size-5" />
        {count > 0 && (
          <span className="absolute right-1 top-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-rose-500 px-1 text-[10px] font-semibold text-white">
            {count > 99 ? "99+" : count}
          </span>
        )}
      </button>

      {open && (
        <>
          <div
            className="fixed inset-0 z-40"
            onClick={() => setOpen(false)}
            aria-hidden
          />
          <div className="absolute right-0 z-50 mt-2 w-[22rem] overflow-hidden rounded-xl border bg-popover text-popover-foreground shadow-xl">
            <div className="flex items-center justify-between border-b px-4 py-2.5">
              <span className="text-sm font-semibold">Notifications</span>
              <button
                type="button"
                disabled={count === 0 || markAll.isPending}
                onClick={() => markAll.mutate()}
                className="flex items-center gap-1 text-xs font-medium text-primary transition-opacity hover:underline disabled:opacity-40"
              >
                <CheckCheck className="size-3.5" />
                Mark all read
              </button>
            </div>

            <div className="flex gap-1 border-b px-2 py-1.5">
              {[
                { key: false, label: "All" },
                { key: true, label: `Unread${count > 0 ? ` (${count})` : ""}` },
              ].map((tab) => (
                <button
                  key={String(tab.key)}
                  type="button"
                  onClick={() => setUnreadOnly(tab.key)}
                  className={cn(
                    "rounded-md px-2.5 py-1 text-xs font-medium transition-colors",
                    unreadOnly === tab.key
                      ? "bg-accent text-foreground"
                      : "text-muted-foreground hover:text-foreground",
                  )}
                >
                  {tab.label}
                </button>
              ))}
            </div>

            <div className="scrollbar-thin max-h-96 overflow-y-auto">
              {items.length === 0 ? (
                <div className="flex flex-col items-center gap-2 px-4 py-10 text-center">
                  <Bell className="size-6 text-muted-foreground/40" />
                  <p className="text-sm text-muted-foreground">
                    {unreadOnly
                      ? "No unread notifications."
                      : "No notifications yet."}
                  </p>
                </div>
              ) : (
                items.map((item) => (
                  <NotificationRow
                    key={item.id}
                    item={item}
                    onRead={() => !item.read && markRead.mutate(item.id)}
                  />
                ))
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
}

function NotificationRow({
  item,
  onRead,
}: {
  item: NotificationItem;
  onRead: () => void;
}) {
  const { icon: Icon, tint } = iconFor(item.type);
  return (
    <button
      type="button"
      onClick={onRead}
      className={cn(
        "flex w-full gap-3 border-b px-4 py-3 text-left transition-colors last:border-b-0 hover:bg-accent",
        !item.read && "bg-primary/5",
      )}
    >
      <span
        className={cn(
          "flex size-8 shrink-0 items-center justify-center rounded-lg",
          tint,
        )}
      >
        <Icon className="size-4" />
      </span>
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span className="truncate text-sm font-medium">{item.title}</span>
          {!item.read && (
            <span className="size-2 shrink-0 rounded-full bg-primary" />
          )}
        </div>
        <p className="mt-0.5 line-clamp-2 text-xs text-muted-foreground">
          {item.body}
        </p>
        <p className="mt-1 text-[10px] text-muted-foreground">
          {formatDate(item.created_at)}
        </p>
      </div>
    </button>
  );
}
