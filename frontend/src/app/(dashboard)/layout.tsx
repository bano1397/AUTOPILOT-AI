import type { ReactNode } from "react";

import { AuthGuard } from "@/components/auth/auth-guard";
import { CommandPalette } from "@/components/command/command-palette";
import { Sidebar } from "@/components/layout/sidebar";
import { Topbar } from "@/components/layout/topbar";

export default function DashboardLayout({ children }: { children: ReactNode }) {
  return (
    <AuthGuard>
      <div className="flex min-h-screen bg-background">
        <Sidebar />
        <div className="flex min-w-0 flex-1 flex-col">
          <Topbar />
          <main className="mx-auto w-full max-w-[1600px] flex-1 p-4 sm:p-6">
            {children}
          </main>
        </div>
      </div>
      <CommandPalette />
    </AuthGuard>
  );
}
