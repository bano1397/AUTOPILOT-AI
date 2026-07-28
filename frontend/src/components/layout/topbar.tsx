"use client";

import { Search, Settings, User as UserIcon } from "lucide-react";
import { useRouter } from "next/navigation";

import { ThemeToggle } from "@/components/common/theme-toggle";
import { MobileNav } from "@/components/layout/mobile-nav";
import { NotificationsBell } from "@/components/layout/notifications-bell";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useHealth } from "@/features/system/hooks";
import { useCommandPalette } from "@/lib/command/store";
import { cn } from "@/lib/utils";

export function Topbar() {
  const router = useRouter();
  const openPalette = useCommandPalette((state) => state.setOpen);
  const health = useHealth();

  const status = health.isError
    ? {
        label: "Offline",
        dot: "bg-rose-500",
        text: "text-rose-600 dark:text-rose-400",
      }
    : health.isLoading
      ? {
          label: "Connecting",
          dot: "bg-amber-500",
          text: "text-amber-600 dark:text-amber-400",
        }
      : {
          label: "Operational",
          dot: "bg-emerald-500",
          text: "text-emerald-600 dark:text-emerald-400",
        };


  return (
    <header className="sticky top-0 z-30 flex h-14 items-center gap-3 border-b bg-background/80 px-4 backdrop-blur md:px-6">
      <MobileNav />

      {/* Global search (opens ⌘K palette) */}
      <button
        type="button"
        onClick={() => openPalette(true)}
        className="flex h-9 w-full max-w-md items-center gap-2 rounded-lg border bg-card px-3 text-sm text-muted-foreground transition-colors hover:border-primary/40 hover:text-foreground"
      >
        <Search className="size-4" />
        <span className="hidden sm:inline">Search or run a command…</span>
        <span className="sm:hidden">Search…</span>
        <kbd className="ml-auto hidden rounded border bg-muted px-1.5 py-0.5 text-[10px] font-medium sm:inline">
          ⌘K
        </kbd>
      </button>

      <div className="flex flex-1 items-center justify-end gap-2 sm:gap-3">
        {/* Live connection status */}
        <div className="hidden items-center gap-2 rounded-full border bg-card px-3 py-1.5 lg:flex">
          <span className={cn("size-2 rounded-full", status.dot)} />
          <span className={cn("text-xs font-medium", status.text)}>
            {status.label}
          </span>
        </div>

        <NotificationsBell />
        <ThemeToggle />

        {/* Profile menu */}
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <button
              type="button"
              className="flex items-center gap-2 rounded-full outline-none ring-offset-background focus-visible:ring-2 focus-visible:ring-ring"
            >
              <Avatar className="size-8">
                <AvatarFallback className="text-xs">AP</AvatarFallback>
              </Avatar>
            </button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-60">
            <DropdownMenuLabel className="flex flex-col gap-0.5">
              <span className="text-sm font-medium text-foreground">
                Shared workspace
              </span>
              <span className="truncate text-xs font-normal">
                Open instance · no sign-in
              </span>
            </DropdownMenuLabel>
            <DropdownMenuSeparator />
            <DropdownMenuItem onClick={() => router.push("/settings")}>
              <UserIcon />
              Profile
            </DropdownMenuItem>
            <DropdownMenuItem onClick={() => router.push("/settings")}>
              <Settings />
              Settings
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </header>
  );
}
