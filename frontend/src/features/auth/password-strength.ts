/** A rough client-side password-strength estimate (not a security guarantee). */
export function scorePassword(password: string): {
  score: 0 | 1 | 2 | 3 | 4;
  label: string;
  color: string;
} {
  let score = 0;
  if (password.length >= 8) score += 1;
  if (password.length >= 12) score += 1;
  if (/[A-Z]/.test(password) && /[a-z]/.test(password)) score += 1;
  if (/\d/.test(password) && /[^A-Za-z0-9]/.test(password)) score += 1;

  const clamped = Math.min(score, 4) as 0 | 1 | 2 | 3 | 4;
  const meta = [
    { label: "Too short", color: "bg-rose-500" },
    { label: "Weak", color: "bg-rose-500" },
    { label: "Fair", color: "bg-amber-500" },
    { label: "Good", color: "bg-indigo-500" },
    { label: "Strong", color: "bg-emerald-500" },
  ][clamped];

  return { score: clamped, label: meta.label, color: meta.color };
}
