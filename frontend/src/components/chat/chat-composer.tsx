"use client";

import { ArrowUp, Loader2 } from "lucide-react";
import { type KeyboardEvent, type ReactNode, useEffect, useRef } from "react";

import { cn } from "@/lib/utils";

/**
 * Auto-resizing chat input. Enter sends; Shift+Enter inserts a newline.
 * `footer` renders inline options (e.g. an approval toggle) below the field.
 */
export function ChatComposer({
  value,
  onChange,
  onSubmit,
  pending,
  placeholder = "Message the AI team…",
  maxLength = 4000,
  footer,
}: {
  value: string;
  onChange: (value: string) => void;
  onSubmit: () => void;
  pending?: boolean;
  placeholder?: string;
  maxLength?: number;
  footer?: ReactNode;
}) {
  const ref = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 200)}px`;
  }, [value]);

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      if (value.trim() && !pending) onSubmit();
    }
  }

  const canSend = Boolean(value.trim()) && !pending;

  return (
    <div className="rounded-2xl border bg-card p-2 shadow-sm focus-within:border-primary/40 focus-within:ring-2 focus-within:ring-primary/10">
      <div className="flex items-end gap-2">
        <textarea
          ref={ref}
          rows={1}
          value={value}
          onChange={(event) => onChange(event.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          maxLength={maxLength}
          className="max-h-[200px] flex-1 resize-none bg-transparent px-2 py-1.5 text-sm outline-none placeholder:text-muted-foreground"
        />
        <button
          type="button"
          onClick={() => canSend && onSubmit()}
          disabled={!canSend}
          aria-label="Send message"
          className={cn(
            "flex size-9 shrink-0 items-center justify-center rounded-xl bg-primary text-primary-foreground transition-opacity",
            !canSend && "opacity-40",
          )}
        >
          {pending ? (
            <Loader2 className="size-4 animate-spin" />
          ) : (
            <ArrowUp className="size-4" />
          )}
        </button>
      </div>
      {footer && (
        <div className="flex items-center justify-between gap-3 px-2 pt-1.5">
          {footer}
          <span className="text-[10px] text-muted-foreground">
            Enter to send · Shift+Enter for a new line
          </span>
        </div>
      )}
    </div>
  );
}
