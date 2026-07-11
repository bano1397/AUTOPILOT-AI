import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { deleteDocument, listDocuments, uploadDocument } from "./api";

const DOCUMENTS_KEY = ["documents"];

/**
 * Paginated document list. Polls every 2s while any visible document is still
 * being ingested, and stops automatically once all are settled.
 */
export function useDocuments(page: number, pageSize = 10) {
  return useQuery({
    queryKey: [...DOCUMENTS_KEY, page, pageSize],
    queryFn: () => listDocuments(page, pageSize),
    refetchInterval: (query) => {
      const items = query.state.data?.data;
      const pending = items?.some(
        (item) => item.status === "uploaded" || item.status === "processing",
      );
      return pending ? 2000 : false;
    },
  });
}

export function useUploadDocument() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (file: File) => uploadDocument(file),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: DOCUMENTS_KEY }),
  });
}

export function useDeleteDocument() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => deleteDocument(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: DOCUMENTS_KEY }),
  });
}
