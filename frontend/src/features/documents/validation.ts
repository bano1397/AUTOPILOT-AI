/** Client-side upload validation for instant feedback; the server remains the
 *  enforcer. The accepted list is configuration-dependent (image types appear
 *  only when OCR is enabled), so callers should pass the server-reported rules
 *  from `useUploadCapabilities`. The constants below are the fallback used
 *  before that request resolves. */

export const ALLOWED_EXTENSIONS = [".pdf", ".docx", ".txt", ".csv", ".xlsx"];
export const MAX_UPLOAD_SIZE_MB = 25;

export interface UploadRules {
  allowedExtensions: string[];
  maxUploadSizeMb: number;
}

export const DEFAULT_UPLOAD_RULES: UploadRules = {
  allowedExtensions: ALLOWED_EXTENSIONS,
  maxUploadSizeMb: MAX_UPLOAD_SIZE_MB,
};

/** Returns an error message, or null when the file is acceptable. */
export function validateFile(
  file: File,
  rules: UploadRules = DEFAULT_UPLOAD_RULES,
): string | null {
  const dot = file.name.lastIndexOf(".");
  const extension = dot === -1 ? "" : file.name.slice(dot).toLowerCase();
  if (!rules.allowedExtensions.includes(extension)) {
    return `Unsupported file type. Allowed: ${rules.allowedExtensions.join(", ")}`;
  }
  if (file.size === 0) {
    return "The file is empty.";
  }
  if (file.size > rules.maxUploadSizeMb * 1024 * 1024) {
    return `File exceeds the ${rules.maxUploadSizeMb} MB limit.`;
  }
  return null;
}
