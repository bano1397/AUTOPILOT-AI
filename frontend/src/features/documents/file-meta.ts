import {
  FileSpreadsheet,
  FileText,
  FileType,
  type LucideIcon,
} from "lucide-react";

/** Maps a filename to a display icon + accent color for cards and rows. */
export function fileMeta(filename: string): {
  icon: LucideIcon;
  tint: string;
  ext: string;
} {
  const dot = filename.lastIndexOf(".");
  const ext = dot === -1 ? "" : filename.slice(dot + 1).toLowerCase();
  switch (ext) {
    case "pdf":
      return { icon: FileType, tint: "text-rose-500 bg-rose-500/10", ext };
    case "csv":
    case "xlsx":
      return {
        icon: FileSpreadsheet,
        tint: "text-emerald-500 bg-emerald-500/10",
        ext,
      };
    case "docx":
      return { icon: FileText, tint: "text-indigo-500 bg-indigo-500/10", ext };
    default:
      return { icon: FileText, tint: "text-slate-500 bg-slate-500/10", ext };
  }
}
