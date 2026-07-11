import { useEffect, useState } from "react";
import { create } from "zustand";
import { createJSONStorage, persist } from "zustand/middleware";

import type { User } from "@/features/auth/types";

interface AuthState {
  accessToken: string | null;
  user: User | null;
  setSession: (payload: { accessToken: string; user: User }) => void;
  setAccessToken: (accessToken: string) => void;
  clear: () => void;
}

/**
 * Client-side auth state. Only the short-lived access token and the user
 * profile are persisted; the refresh token lives exclusively in an httpOnly
 * cookie set by the backend, out of reach of any script (XSS hardening).
 */
export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      accessToken: null,
      user: null,
      setSession: ({ accessToken, user }) => set({ accessToken, user }),
      setAccessToken: (accessToken) => set({ accessToken }),
      clear: () => set({ accessToken: null, user: null }),
    }),
    {
      name: "autopilot-auth",
      storage: createJSONStorage(() => localStorage),
      partialize: (state) => ({
        accessToken: state.accessToken,
        user: state.user,
      }),
    },
  ),
);

/** Returns true once the persisted store has rehydrated on the client. */
export function useAuthHydrated(): boolean {
  // Start false so server prerender never touches the client-only persist API.
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    const markHydrated = () => setHydrated(true);
    const unsubscribe = useAuthStore.persist.onFinishHydration(markHydrated);
    if (useAuthStore.persist.hasHydrated()) markHydrated();
    return unsubscribe;
  }, []);

  return hydrated;
}
