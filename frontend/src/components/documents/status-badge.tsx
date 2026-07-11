import { Badge } from "@/components/ui/badge";
import type { DocumentStatus } from "@/features/documents/types";

const STATUS_CONFIG: Record<
  DocumentStatus,
  {
    label: string;
    variant: "success" | "warning" | "destructive";
    pulse?: boolean;
  }
> = {
  uploaded: { label: "Queued", variant: "warning", pulse: true },
  processing: { label: "Processing", variant: "warning", pulse: true },
  indexed: { label: "Indexed", variant: "success" },
  failed: { label: "Failed", variant: "destructive" },
};

export function StatusBadge({ status }: { status: DocumentStatus }) {
  const config = STATUS_CONFIG[status];
  return (
    <Badge
      variant={config.variant}
      className={config.pulse ? "animate-pulse" : undefined}
    >
      {config.label}
    </Badge>
  );
}
