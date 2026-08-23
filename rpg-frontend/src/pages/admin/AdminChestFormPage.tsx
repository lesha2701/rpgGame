import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { ErrorState, Skeleton } from "@/components/ui";
import { ImageUploadField } from "@/components/admin/ImageUploadField";
import { useAdminChests, useCreateChest, useUpdateChest } from "@/hooks/useAdminChests";
import type { Rarity } from "@/types";

const RARITIES: Rarity[] = ["common", "rare", "epic", "legendary"];
const RARITY_LABEL: Record<Rarity, string> = { common: "Обычная", rare: "Редкая", epic: "Эпическая", legendary: "Легендарная" };

interface FormState {
  slug: string;
  name: string;
  description: string;
  price: number;
  is_active: boolean;
  probabilities: Record<Rarity, string>;
}

const EMPTY: FormState = {
  slug: "",
  name: "",
  description: "",
  price: 100,
  is_active: true,
  probabilities: { common: "0.60", rare: "0.25", epic: "0.12", legendary: "0.03" },
};

export function AdminChestFormPage() {
  const { chestId } = useParams<{ chestId: string }>();
  const isEdit = Boolean(chestId);
  const navigate = useNavigate();

  const chests = useAdminChests();
  const createChest = useCreateChest();
  const updateChest = useUpdateChest();

  const existing = isEdit ? chests.data?.find((c) => c.id === Number(chestId)) : undefined;
  const [form, setForm] = useState<FormState>(EMPTY);

  useEffect(() => {
    if (existing) {
      const probs = { ...EMPTY.probabilities };
      for (const p of existing.rarity_probabilities) probs[p.rarity] = String(p.probability);
      setForm({
        slug: existing.slug,
        name: existing.name,
        description: existing.description,
        price: existing.price,
        is_active: existing.is_active,
        probabilities: probs,
      });
    }
  }, [existing]);

  const probabilitySum = useMemo(
    () => RARITIES.reduce((sum, r) => sum + (Number(form.probabilities[r]) || 0), 0),
    [form.probabilities],
  );
  const sumOk = probabilitySum >= 0.98 && probabilitySum <= 1.02;

  const mutation = isEdit ? updateChest : createChest;

  function submit() {
    const rarity_probabilities = RARITIES.map((rarity) => ({ rarity, probability: Number(form.probabilities[rarity]) || 0 }));

    if (isEdit && existing) {
      updateChest.mutate(
        {
          id: existing.id,
          payload: {
            name: form.name,
            description: form.description,
            price: form.price,
            is_active: form.is_active,
            rarity_probabilities,
          },
        },
        { onSuccess: () => navigate("/admin/chests") },
      );
    } else {
      createChest.mutate(
        {
          slug: form.slug,
          name: form.name,
          description: form.description,
          price: form.price,
          is_active: form.is_active,
          rarity_probabilities,
        },
        { onSuccess: () => navigate("/admin/chests") },
      );
    }
  }

  if (isEdit && chests.isPending) {
    return <Skeleton className="h-64" />;
  }
  if (isEdit && !existing && !chests.isPending) {
    return <ErrorState error={new Error("chest not found")} />;
  }

  return (
    <div className="max-w-lg">
      <h1 className="mb-1 font-display text-2xl font-semibold text-ink">{isEdit ? "Изменить сундук" : "Новый сундук"}</h1>
      <p className="mb-4 font-mono text-[10.5px] text-ink-dim">
        Тир предмета ограничен тиром героя, который открывает сундук (1..текущий тир) — у сундука больше нет своего
        тира. Сундуки различаются только ценой и шансами на редкие предметы.
      </p>

      <div className="flex flex-col gap-3">
        {isEdit && existing && (
          <ImageUploadField
            basePath="/admin/chests"
            resourceId={existing.id}
            currentImagePath={existing.image_path}
            queryKey="chests"
          />
        )}

        {!isEdit && (
          <label className="flex flex-col gap-1">
            <span className="font-mono text-[10px] uppercase text-ink-dim">Slug</span>
            <input
              value={form.slug}
              onChange={(e) => setForm({ ...form, slug: e.target.value })}
              className="rounded-md border border-hairline bg-bg-raised px-3 py-2 text-[13px] text-ink outline-none"
            />
          </label>
        )}

        <label className="flex flex-col gap-1">
          <span className="font-mono text-[10px] uppercase text-ink-dim">Название</span>
          <input
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
            className="rounded-md border border-hairline bg-bg-raised px-3 py-2 text-[13px] text-ink outline-none"
          />
        </label>

        <label className="flex flex-col gap-1">
          <span className="font-mono text-[10px] uppercase text-ink-dim">Описание</span>
          <textarea
            value={form.description}
            onChange={(e) => setForm({ ...form, description: e.target.value })}
            rows={2}
            className="rounded-md border border-hairline bg-bg-raised px-3 py-2 text-[13px] text-ink outline-none"
          />
        </label>

        <label className="flex flex-col gap-1">
          <span className="font-mono text-[10px] uppercase text-ink-dim">Цена</span>
          <input
            type="number"
            min={0}
            value={form.price}
            onChange={(e) => setForm({ ...form, price: Number(e.target.value) })}
            className="rounded-md border border-hairline bg-bg-raised px-3 py-2 text-[13px] text-ink outline-none"
          />
        </label>

        <label className="flex items-center gap-2">
          <input
            type="checkbox"
            checked={form.is_active}
            onChange={(e) => setForm({ ...form, is_active: e.target.checked })}
          />
          <span className="text-[12.5px] text-ink">Активен</span>
        </label>

        <div>
          <p className="mb-2 font-mono text-[10px] uppercase text-ink-dim">
            Вероятности редкости (сумма должна быть ≈ 1.0 — сейчас {probabilitySum.toFixed(2)})
          </p>
          <div className="grid grid-cols-2 gap-2">
            {RARITIES.map((r) => (
              <label key={r} className="flex items-center justify-between gap-2 rounded-md border border-hairline bg-bg-raised px-3 py-2">
                <span className="text-[11.5px] text-ink-mute">{RARITY_LABEL[r]}</span>
                <input
                  type="number"
                  step="0.01"
                  min={0}
                  max={1}
                  value={form.probabilities[r]}
                  onChange={(e) => setForm({ ...form, probabilities: { ...form.probabilities, [r]: e.target.value } })}
                  className="w-16 bg-transparent text-right font-mono text-[12px] text-ink outline-none"
                />
              </label>
            ))}
          </div>
          {!sumOk && <p className="mt-1 font-mono text-[10.5px] text-crimson-bright">Сумма не равна 1.0 — сервер отклонит.</p>}
        </div>

        {mutation.isError && <ErrorState error={mutation.error} />}

        <button
          onClick={submit}
          disabled={mutation.isPending || !sumOk || !form.name || (!isEdit && !form.slug)}
          className="mt-2 rounded-md bg-gradient-to-b from-ember-bright to-ember py-2.5 font-mono text-[12px] font-bold text-[#1D1204] disabled:opacity-40"
        >
          {mutation.isPending ? "Сохранение..." : isEdit ? "Сохранить" : "Создать"}
        </button>
      </div>
    </div>
  );
}
