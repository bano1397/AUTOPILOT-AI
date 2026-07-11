"use client";

import { motion } from "framer-motion";
import { Loader2, UploadCloud } from "lucide-react";
import { type DragEvent, useRef, useState } from "react";
import { toast } from "sonner";

import { useUploadDocument } from "@/features/documents/hooks";
import {
  ALLOWED_EXTENSIONS,
  MAX_UPLOAD_SIZE_MB,
  validateFile,
} from "@/features/documents/validation";
import { ApiError } from "@/lib/api/types";
import { cn } from "@/lib/utils";

export function DocumentDropzone() {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const [uploading, setUploading] = useState(0);
  const upload = useUploadDocument();

  async function handleFiles(files: FileList | null) {
    if (!files || files.length === 0) return;
    for (const file of Array.from(files)) {
      const problem = validateFile(file);
      if (problem) {
        toast.error(`${file.name}: ${problem}`);
        continue;
      }
      setUploading((n) => n + 1);
      try {
        await upload.mutateAsync(file);
        toast.success(`${file.name} uploaded — indexing started`);
      } catch (error) {
        toast.error(
          `${file.name}: ${error instanceof ApiError ? error.message : "Upload failed"}`,
        );
      } finally {
        setUploading((n) => n - 1);
      }
    }
  }

  function onDrop(event: DragEvent) {
    event.preventDefault();
    setDragging(false);
    void handleFiles(event.dataTransfer.files);
  }

  const busy = uploading > 0;

  return (
    <div
      role="button"
      tabIndex={0}
      onClick={() => inputRef.current?.click()}
      onKeyDown={(e) => e.key === "Enter" && inputRef.current?.click()}
      onDragOver={(e) => {
        e.preventDefault();
        setDragging(true);
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={onDrop}
      className={cn(
        "relative flex cursor-pointer flex-col items-center justify-center gap-2 rounded-2xl border-2 border-dashed p-8 text-center outline-none transition-colors focus-visible:ring-2 focus-visible:ring-ring",
        dragging
          ? "border-primary bg-primary/5"
          : "border-border hover:border-primary/40 hover:bg-accent/40",
      )}
    >
      <input
        ref={inputRef}
        type="file"
        multiple
        accept={ALLOWED_EXTENSIONS.join(",")}
        className="hidden"
        onChange={(event) => {
          void handleFiles(event.target.files);
          event.target.value = "";
        }}
      />
      <motion.div
        animate={dragging ? { y: -4, scale: 1.05 } : { y: 0, scale: 1 }}
        className="flex size-12 items-center justify-center rounded-xl bg-primary/10 text-primary"
      >
        {busy ? (
          <Loader2 className="size-6 animate-spin" />
        ) : (
          <UploadCloud className="size-6" />
        )}
      </motion.div>
      <p className="text-sm font-medium">
        {busy
          ? `Uploading ${uploading} file${uploading === 1 ? "" : "s"}…`
          : dragging
            ? "Drop to upload"
            : "Drag & drop files, or click to browse"}
      </p>
      <p className="text-xs text-muted-foreground">
        {ALLOWED_EXTENSIONS.join(", ")} · up to {MAX_UPLOAD_SIZE_MB} MB each
      </p>
      {busy && (
        <div className="mt-1 h-1 w-40 overflow-hidden rounded-full bg-muted">
          <motion.div
            className="h-full w-1/2 rounded-full bg-primary"
            animate={{ x: ["-100%", "200%"] }}
            transition={{ duration: 1.1, repeat: Infinity, ease: "easeInOut" }}
          />
        </div>
      )}
    </div>
  );
}
