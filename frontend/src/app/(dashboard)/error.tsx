"use client";

import { useEffect } from "react";

import { Button } from "@/components/ui/button";

/** Route-level error boundary for the dashboard segment. */
export default function DashboardError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    // Surfaced in the browser console for debugging; no PII is logged.
    console.error(error);
  }, [error]);

  return (
    <div className="flex flex-col items-center justify-center gap-4 py-24 text-center">
      <h1 className="text-xl font-semibold">Something went wrong</h1>
      <p className="max-w-md text-muted-foreground">
        This section failed to load. You can retry, or head back to the
        dashboard.
      </p>
      <Button onClick={reset}>Try again</Button>
    </div>
  );
}
