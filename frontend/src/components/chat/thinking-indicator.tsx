"use client";

import { motion } from "framer-motion";
import { Bot } from "lucide-react";

/** Animated "the agent team is working" placeholder shown while a reply streams in. */
export function ThinkingIndicator({ label }: { label?: string }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      className="flex items-center gap-3"
    >
      <div className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-gradient-to-br from-indigo-500 to-violet-600 text-white">
        <Bot className="size-4" />
      </div>
      <div className="flex items-center gap-2 rounded-2xl rounded-tl-sm border bg-card px-4 py-3">
        <div className="flex gap-1">
          {[0, 1, 2].map((i) => (
            <motion.span
              key={i}
              className="size-1.5 rounded-full bg-muted-foreground/60"
              animate={{ opacity: [0.3, 1, 0.3], y: [0, -2, 0] }}
              transition={{
                duration: 1,
                repeat: Infinity,
                delay: i * 0.15,
                ease: "easeInOut",
              }}
            />
          ))}
        </div>
        <span className="text-xs text-muted-foreground">
          {label ?? "Routing to the right agent…"}
        </span>
      </div>
    </motion.div>
  );
}
