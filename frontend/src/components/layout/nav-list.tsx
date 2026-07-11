"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { cn } from "@/lib/utils";

import { navItems } from "./nav-items";

/** The dashboard navigation links, shared by the desktop sidebar and mobile menu. */
export function NavList({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname();

  return (
    <nav className="space-y-1 px-3 py-2">
      {navItems.map((item) => {
        const Icon = item.icon;

        if (item.disabled) {
          return (
            <span
              key={item.label}
              className="flex cursor-not-allowed items-center gap-3 rounded-md px-3 py-2 text-sm text-muted-foreground/50"
              title="Coming soon"
            >
              <Icon className="size-4" />
              {item.label}
            </span>
          );
        }

        const active = pathname === item.href;
        return (
          <Link
            key={item.href}
            href={item.href}
            onClick={onNavigate}
            aria-current={active ? "page" : undefined}
            className={cn(
              "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium text-muted-foreground transition-colors",
              active
                ? "bg-primary/10 text-primary"
                : "hover:bg-accent hover:text-foreground",
            )}
          >
            <Icon className="size-4" />
            {item.label}
          </Link>
        );
      })}
    </nav>
  );
}
