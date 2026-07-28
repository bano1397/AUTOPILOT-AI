export type Theme = "light" | "dark" | "system";

/** Instance-wide preferences (there are no per-user accounts). */
export interface Preferences {
  theme: Theme;
  default_top_k: number;
  require_approval_by_default: boolean;
  notifications_enabled: boolean;
}

export type PreferencesUpdate = Partial<Preferences>;
