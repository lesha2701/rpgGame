import { useQuery } from "@tanstack/react-query";

import { catalogApi } from "@/services/api";

export function useHeroTemplates() {
  return useQuery({ queryKey: ["hero-templates"], queryFn: catalogApi.getHeroTemplates });
}

export function useRaces() {
  return useQuery({ queryKey: ["races"], queryFn: catalogApi.getRaces });
}

export function useClasses() {
  return useQuery({ queryKey: ["classes"], queryFn: catalogApi.getClasses });
}
