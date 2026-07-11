"use client";

import { type ReactNode, useEffect, useState } from "react";

import { getMe } from "@/features/auth/api";
import { useAuthStore } from "@/lib/auth/store";

/**
 * Authentication is disabled for the public demo. Rather than gate access, this
 * bootstraps the shared "public workspace" user from the backend (which no
 * longer requires a token) so the UI has an identity to display, then always
 * renders the app.
 */
export function AuthGuard({ children }: { children: ReactNode }) {
  const user = useAuthStore((state) => state.user);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    if (user) {
      setReady(true);
      return;
    }
    let active = true;
    getMe()
      .then((me) => {
        if (active) useAuthStore.setState({ user: me });
      })
      .catch(() => undefined)
      .finally(() => {
        if (active) setReady(true);
      });
    return () => {
      active = false;
    };
  }, [user]);

  if (!ready) {
    return (
      <div className="flex min-h-screen items-center justify-center text-sm text-muted-foreground">
        Loading…
      </div>
    );
  }

  return <>{children}</>;
}
