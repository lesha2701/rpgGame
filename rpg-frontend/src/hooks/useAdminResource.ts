import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { makeAdminResourceApi } from "@/services/api/adminCatalog";

export function makeAdminResourceHooks<TOut, TCreate, TUpdate>(queryKey: string, basePath: string) {
  const resourceApi = makeAdminResourceApi<TOut, TCreate, TUpdate>(basePath);

  function useList() {
    return useQuery({ queryKey: ["admin", queryKey], queryFn: resourceApi.list });
  }

  function useInvalidate() {
    const queryClient = useQueryClient();
    return () => queryClient.invalidateQueries({ queryKey: ["admin", queryKey] });
  }

  function useCreate() {
    const invalidate = useInvalidate();
    return useMutation({ mutationFn: resourceApi.create, onSuccess: invalidate });
  }

  function useUpdate() {
    const invalidate = useInvalidate();
    return useMutation({
      mutationFn: ({ id, payload }: { id: number; payload: TUpdate }) => resourceApi.update(id, payload),
      onSuccess: invalidate,
    });
  }

  function useToggleActive() {
    const invalidate = useInvalidate();
    return useMutation({ mutationFn: resourceApi.toggleActive, onSuccess: invalidate });
  }

  return { useList, useCreate, useUpdate, useToggleActive };
}
