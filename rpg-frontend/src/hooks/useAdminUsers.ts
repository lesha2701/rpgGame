import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { adminUsersApi } from "@/services/api";

export function useUserList(search: string, limit: number, offset: number) {
  return useQuery({
    queryKey: ["admin", "users", "list", search, limit, offset],
    queryFn: () => adminUsersApi.listUsers(search, limit, offset),
  });
}

export function useUserStats() {
  return useQuery({ queryKey: ["admin", "users", "stats"], queryFn: adminUsersApi.getUserStats });
}

export function useUserDetail(id: number) {
  return useQuery({ queryKey: ["admin", "users", "detail", id], queryFn: () => adminUsersApi.getUserDetail(id) });
}

function useInvalidateUsers() {
  const queryClient = useQueryClient();
  return () => queryClient.invalidateQueries({ queryKey: ["admin", "users"] });
}

export function useGrantCoins() {
  const invalidate = useInvalidateUsers();
  return useMutation({
    mutationFn: ({ id, amount, description }: { id: number; amount: number; description: string }) =>
      adminUsersApi.grantCoins(id, amount, description),
    onSuccess: invalidate,
  });
}

export function useDeductCoins() {
  const invalidate = useInvalidateUsers();
  return useMutation({
    mutationFn: ({ id, amount, description }: { id: number; amount: number; description: string }) =>
      adminUsersApi.deductCoins(id, amount, description),
    onSuccess: invalidate,
  });
}

export function useToggleBan() {
  const invalidate = useInvalidateUsers();
  return useMutation({ mutationFn: adminUsersApi.toggleBan, onSuccess: invalidate });
}
