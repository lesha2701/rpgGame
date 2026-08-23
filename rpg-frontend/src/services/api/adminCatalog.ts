import { api } from "./client";

/** All 7 catalog admin routers share the exact same shape
 * (GET list / POST create / PUT update / POST {id}/toggle-active) — see
 * rpg-backend's admin_races.py, admin_classes.py, etc., each a structural
 * copy of admin_chests.py. One factory instead of 7 near-identical modules. */
export function makeAdminResourceApi<TOut, TCreate, TUpdate>(basePath: string) {
  return {
    list: async (): Promise<TOut[]> => {
      const { data } = await api.get<TOut[]>(basePath);
      return data;
    },
    create: async (payload: TCreate): Promise<TOut> => {
      const { data } = await api.post<TOut>(basePath, payload);
      return data;
    },
    update: async (id: number, payload: TUpdate): Promise<TOut> => {
      const { data } = await api.put<TOut>(`${basePath}/${id}`, payload);
      return data;
    },
    toggleActive: async (id: number): Promise<TOut> => {
      const { data } = await api.post<TOut>(`${basePath}/${id}/toggle-active`);
      return data;
    },
  };
}
