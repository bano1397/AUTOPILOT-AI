/** Client-side upload validation mirroring the backend rules (instant feedback;
 *  the server remains the enforcer). */

export const ALLOWED_EXTENSIONS = [".pdf", ".docx", ".txt", ".csv", ".xlsx"];
export const MAX_UPLOAD_SIZE_MB = 25;

/** Returns an error message, or null when the file is acceptable. */
export function validateFile(file: File): string | null {
  const dot = file.name.lastIndexOf(".");
  const extension = dot === -1 ? "" : file.name.slice(dot).toLowerCase();
  if (!ALLOWED_EXTENSIONS.includes(extension)) {
    return `Unsupported file type. Allowed: ${ALLOWED_EXTENSIONS.join(", ")}`;
  }
  if (file.size === 0) {
    return "The file is empty.";
  }
  if (file.size > MAX_UPLOAD_SIZE_MB * 1024 * 1024) {
    return `File exceeds the ${MAX_UPLOAD_SIZE_MB} MB limit.`;
  }
  return null;
}
