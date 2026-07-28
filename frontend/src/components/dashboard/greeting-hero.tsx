"use client";

import { motion } from "framer-motion";
import { useEffect, useState } from "react";

function greetingFor(hour: number): string {
  if (hour < 12) return "Good morning";
  if (hour < 18) return "Good afternoon";
  return "Good evening";
}

export function GreetingHero() {
  // No accounts exist, so there is no name to greet — the shared workspace
  // identity is not a person (docs/COMPLETION_PLAN.md §3).
  const [now, setNow] = useState<Date | null>(null);

  // Rendered only after mount so server and client markup match.
  useEffect(() => {
    setNow(new Date());
    const timer = setInterval(() => setNow(new Date()), 30_000);
    return () => clearInterval(timer);
  }, []);

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35 }}
    >
      <p className="text-sm text-muted-foreground">
        {now
          ? now.toLocaleDateString(undefined, {
              weekday: "long",
              month: "long",
              day: "numeric",
            })
          : " "}
      </p>
      <h1 className="mt-1 text-3xl font-semibold tracking-tight">
        {now ? greetingFor(now.getHours()) : "Welcome"}
      </h1>
      <p className="mt-1 text-muted-foreground">
        Your enterprise AI automation platform — here’s what’s happening.
      </p>
    </motion.div>
  );
}
