import { useMutation, useQueryClient } from "@tanstack/react-query";

import { heroesApi } from "@/services/api";

/** Invalidates ["session"] on success — SessionGate's useSession() call
 * refetches and picks up the new active_hero, which is what un-blocks
 * navigation past the character-creation gate. */
export function useCreateHero() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ heroTemplateId, name }: { heroTemplateId: number; name: string }) =>
      heroesApi.createHero(heroTemplateId, name),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["session"] });
    },
  });
}
