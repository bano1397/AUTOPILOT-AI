import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  discardDraft,
  listEmails,
  retriageEmail,
  sendReply,
  syncMailbox,
} from "./api";
import type { EmailStatus } from "./types";

const EMAILS_KEY = ["emails"] as const;

export function useEmails(page = 1, status?: EmailStatus) {
  return useQuery({
    queryKey: [...EMAILS_KEY, page, status ?? "all"],
    queryFn: () => listEmails(page, status),
  });
}

/** Every mutation refreshes the list, since triage changes status and drafts.
 *
 * Generic over the result as well as the argument so callers keep their typed
 * response (the sync summary, the updated email) instead of `unknown`.
 */
function useEmailMutation<TArgs, TResult>(
  fn: (args: TArgs) => Promise<TResult>,
) {
  const queryClient = useQueryClient();
  return useMutation<TResult, Error, TArgs>({
    mutationFn: fn,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: EMAILS_KEY }),
  });
}

export function useSyncMailbox() {
  return useEmailMutation(() => syncMailbox());
}

export function useSendReply() {
  return useEmailMutation(({ id, body }: { id: string; body?: string }) =>
    sendReply(id, body),
  );
}

export function useDiscardDraft() {
  return useEmailMutation((id: string) => discardDraft(id));
}

export function useRetriageEmail() {
  return useEmailMutation((id: string) => retriageEmail(id));
}
