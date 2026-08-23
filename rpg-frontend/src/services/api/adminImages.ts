import { api } from "./client";

/** POSTs a multipart file to `{basePath}/{id}/image` — the shape every one
 * of the four upload-capable admin routers shares (see rpg-backend's
 * admin_hero_templates.py, admin_enemies.py, admin_items.py,
 * admin_expeditions.py). Returns the updated resource as `unknown`; callers
 * already know the concrete type from their own resource config. */
export async function uploadResourceImage(basePath: string, id: number, file: File): Promise<unknown> {
  const formData = new FormData();
  formData.append("file", file);
  const { data } = await api.post(`${basePath}/${id}/image`, formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return data;
}
