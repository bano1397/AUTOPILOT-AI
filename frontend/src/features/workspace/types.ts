/** The single shared identity the whole instance runs as (no accounts). */
export interface WorkspaceUser {
  id: string;
  email: string;
  is_active: boolean;
  created_at: string;
}
