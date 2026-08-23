import { useRef, useState, type ChangeEvent } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { uploadResourceImage } from "@/services/api/adminImages";
import { staticUrl } from "@/utils/staticUrl";

interface ImageUploadFieldProps {
  basePath: string;
  resourceId: number;
  currentImagePath: string | null;
  queryKey: string;
}

export function ImageUploadField({ basePath, resourceId, currentImagePath, queryKey }: ImageUploadFieldProps) {
  const queryClient = useQueryClient();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);

  async function handleFileChange(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;

    setPreviewUrl(URL.createObjectURL(file));
    setUploading(true);
    setError(null);
    try {
      await uploadResourceImage(basePath, resourceId, file);
      await queryClient.invalidateQueries({ queryKey: ["admin", queryKey] });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось загрузить изображение");
    } finally {
      setUploading(false);
    }
  }

  const displayUrl = previewUrl ?? staticUrl(currentImagePath);

  return (
    <div className="flex flex-col gap-2">
      <span className="font-mono text-[10px] uppercase text-ink-dim">Изображение</span>
      <div className="flex items-center gap-3">
        <div className="flex h-20 w-20 flex-none items-center justify-center overflow-hidden rounded-md border border-hairline bg-bg-raised">
          {displayUrl ? (
            <img src={displayUrl} alt="" className="h-full w-full object-cover" />
          ) : (
            <span className="text-lg opacity-30">🖼</span>
          )}
        </div>
        <div className="flex flex-col gap-1.5">
          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            disabled={uploading}
            className="rounded-md border border-hairline bg-bg-raised px-3 py-1.5 font-mono text-[10.5px] text-ink disabled:opacity-50"
          >
            {uploading ? "Загрузка..." : "Выбрать файл"}
          </button>
          <span className="font-mono text-[9px] text-ink-dim">PNG/JPG/WEBP, до 5МБ</span>
        </div>
        <input ref={fileInputRef} type="file" accept="image/png,image/jpeg,image/webp" onChange={handleFileChange} className="hidden" />
      </div>
      {error && <p className="font-mono text-[10.5px] text-crimson-bright">{error}</p>}
    </div>
  );
}
