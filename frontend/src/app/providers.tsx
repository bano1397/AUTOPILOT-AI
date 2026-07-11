"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ThemeProvider } from "next-themes";
import { Toaster } from "sonner";
import { type ReactNode, useEffect, useState } from "react";

import { useChatStore } from "@/lib/chat/store";

/** Global client-side providers: theming (dark mode) and server-state cache. */
export function Providers({ children }: { children: ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 60_000,
            retry: 1,
            refetchOnWindowFocus: false,
          },
        },
      }),
  );

  // Restore per-tab chat state after mount (skipped during SSR/hydration so
  // server and client markup match).
  useEffect(() => {
    void useChatStore.persist.rehydrate();
  }, []);

  return (
    <ThemeProvider
      attribute="class"
      defaultTheme="system"
      enableSystem
      disableTransitionOnChange
    >
      <QueryClientProvider client={queryClient}>
        {children}
        <Toaster
          position="bottom-right"
          toastOptions={{
            classNames: {
              toast:
                "!rounded-xl !border !border-border !bg-card !text-card-foreground !shadow-lg",
            },
          }}
        />
      </QueryClientProvider>
    </ThemeProvider>
  );
}
