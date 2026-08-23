import { useQuery } from "@tanstack/react-query";

import { skillsApi } from "@/services/api";

export function useMySkills() {
  return useQuery({ queryKey: ["skills", "me"], queryFn: skillsApi.getMySkills });
}
