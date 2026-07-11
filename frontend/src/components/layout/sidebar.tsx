"use client";

import { PanelLeftClose, PanelLeftOpen, Search, Sparkles } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";

import {
  navGroups,
  type NavItem,
  settingsNavItem,
} from "@/components/layout/nav-items";
import { Badge } from "@/components/ui/badge";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { usePendingApprovals } from "@/features/approvals/hooks";
import { useCommandPalette } from "@/lib/command/store";
import { cn } from "@/lib/utils";

const COLLAPSE_KEY = "ap-sidebar-collapsed";

export function Sidebar() {
  const pathname = usePathname();
  const openPalette = useCommandPalette((state) => state.setOpen);
  const approvals = usePendingApprovals(1);
  const pendingApprovals = approvals.data?.meta?.total ?? 0;

  const [collapsed, setCollapsed] = useState(false);
  useEffect(() => {
    setCollapsed(localStorage.getItem(COLLAPSE_KEY) === "1");
  }, []);

  function toggleCollapsed() {
    setCollapsed((prev) => {
      const next = !prev;
      localStorage.setItem(COLLAPSE_KEY, next ? "1" : "0");
      return next;
    });
  }

  const badgeFor = (item: NavItem) =>
    item.badgeKey === "approvals" && pendingApprovals > 0
      ? pendingApprovals
      : undefined;

  return (
    <TooltipProvider delayDuration={0}>
      <aside
        className={cn(
          "sticky top-0 hidden h-screen shrink-0 flex-col border-r bg-card transition-[width] duration-200 md:flex",
          collapsed ? "w-[4.5rem]" : "w-64",
        )}
      >
        {/* Brand */}
        <div
          className={cn(
            "flex h-14 items-center border-b px-3",
            collapsed ? "justify-center" : "gap-2.5",
          )}
        >
          <div className="flex size-9 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-indigo-500 to-violet-600 text-white shadow-sm">
            <Sparkles className="size-5" />
          </div>
          {!collapsed && (
            <div className="leading-tight">
              <p className="text-sm font-semibold tracking-tight">
                AutoPilot AI
              </p>
              <p className="text-[10px] text-muted-foreground">
                Enterprise automation
              </p>
            </div>
          )}
        </div>

        {/* Search / ⌘K */}
        <div className="px-3 pt-3">
          <button
            type="button"
            onClick={() => openPalette(true)}
            className={cn(
              "flex h-9 w-full items-center gap-2 rounded-lg border bg-background text-sm text-muted-foreground transition-colors hover:border-primary/40 hover:text-foreground",
              collapsed ? "justify-center px-0" : "px-2.5",
            )}
          >
            <Search className="size-4 shrink-0" />
            {!collapsed && (
              <>
                <span>Search…</span>
                <kbd className="ml-auto rounded border bg-muted px-1.5 py-0.5 text-[10px] font-medium">
                  ⌘K
                </kbd>
              </>
            )}
          </button>
        </div>

        {/* Navigation */}
        <nav className="scrollbar-thin flex-1 space-y-4 overflow-y-auto px-3 py-4">
          {navGroups.map((group) => (
            <div key={group.label} className="space-y-1">
              {!collapsed && (
                <p className="px-2 pb-1 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground/70">
                  {group.label}
                </p>
              )}
              {group.items.map((item) => (
                <NavLink
                  key={item.href}
                  item={item}
                  active={pathname === item.href}
                  collapsed={collapsed}
                  badge={badgeFor(item)}
                />
              ))}
            </div>
          ))}
        </nav>

        {/* Footer: settings + collapse toggle */}
        <div className="space-y-1 border-t p-3">
          <NavLink
            item={settingsNavItem}
            active={pathname === settingsNavItem.href}
            collapsed={collapsed}
          />
          <button
            type="button"
            onClick={toggleCollapsed}
            className={cn(
              "flex h-9 w-full items-center gap-3 rounded-lg px-2.5 text-sm font-medium text-muted-foreground transition-colors hover:bg-accent hover:text-foreground",
              collapsed && "justify-center px-0",
            )}
          >
            {collapsed ? (
              <PanelLeftOpen className="size-4" />
            ) : (
              <>
                <PanelLeftClose className="size-4" />
                <span>Collapse</span>
              </>
            )}
          </button>
        </div>
      </aside>
    </TooltipProvider>
  );
}

function NavLink({
  item,
  active,
  collapsed,
  badge,
}: {
  item: NavItem;
  active: boolean;
  collapsed: boolean;
  badge?: number;
}) {
  const Icon = item.icon;
  const link = (
    <Link
      href={item.href}
      aria-current={active ? "page" : undefined}
      className={cn(
        "group relative flex h-9 items-center gap-3 rounded-lg px-2.5 text-sm font-medium transition-colors",
        collapsed && "justify-center px-0",
        active
          ? "bg-primary/10 text-primary"
          : "text-muted-foreground hover:bg-accent hover:text-foreground",
      )}
    >
      {active && (
        <span className="absolute left-0 top-1/2 h-5 w-1 -translate-y-1/2 rounded-r-full bg-primary" />
      )}
      <Icon className="size-4 shrink-0" />
      {!collapsed && <span className="truncate">{item.label}</span>}
      {!collapsed && badge !== undefined && (
        <Badge
          className="ml-auto h-5 min-w-5 justify-center px-1.5"
          variant="default"
        >
          {badge}
        </Badge>
      )}
      {collapsed && badge !== undefined && (
        <span className="absolute right-1 top-1 size-2 rounded-full bg-primary" />
      )}
    </Link>
  );

  if (!collapsed) return link;

  return (
    <Tooltip>
      <TooltipTrigger asChild>{link}</TooltipTrigger>
      <TooltipContent side="right">
        {item.label}
        {badge !== undefined ? ` · ${badge}` : ""}
      </TooltipContent>
    </Tooltip>
  );
}
