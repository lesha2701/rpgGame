import { useState } from "react";

import { CharacterArtwork } from "@/components/artwork";
import { Button, ErrorState, Skeleton } from "@/components/ui";
import { useCreateHero } from "@/hooks/useHeroes";
import { useHeroTemplates } from "@/hooks/useCatalog";
import type { HeroTemplateOut } from "@/types";
import { heroTagline } from "@/utils/format";

const NAME_MIN_LENGTH = 2;
const NAME_MAX_LENGTH = 20;

function TemplateCard({
  template,
  selected,
  onSelect,
}: {
  template: HeroTemplateOut;
  selected: boolean;
  onSelect: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onSelect}
      className={`flex flex-col gap-1.5 rounded-lg p-1.5 text-left transition-colors ${
        selected ? "bg-ember/15 ring-2 ring-ember" : "ring-1 ring-hairline"
      }`}
    >
      <CharacterArtwork template={template} size="card" />
      <div className="px-0.5 pb-0.5">
        <p className="truncate font-display text-[13px] font-semibold text-ink">{template.name}</p>
        <p className="truncate font-mono text-[9.5px] uppercase tracking-wide text-ink-mute">
          {heroTagline(template.race.name, template.character_class.name)}
        </p>
      </div>
    </button>
  );
}

/** Mandatory onboarding gate: SessionGate renders this instead of the app
 * shell whenever session.data.user.active_hero is null, so it is the only
 * thing a brand-new player can see — no bottom nav, no route escape hatch —
 * until they pick a template and name their hero. Naming is required here
 * (not optional) precisely so every hero has its own identity distinct from
 * the shared HeroTemplate.name; see leaderboard_service's use of it. */
export function CharacterCreationScreen() {
  const templates = useHeroTemplates();
  const createHero = useCreateHero();
  const [selectedTemplateId, setSelectedTemplateId] = useState<number | null>(null);
  const [name, setName] = useState("");

  const trimmedName = name.trim();
  const nameValid = trimmedName.length >= NAME_MIN_LENGTH && trimmedName.length <= NAME_MAX_LENGTH;
  const canSubmit = selectedTemplateId !== null && nameValid && !createHero.isPending;

  function handleSubmit() {
    if (!canSubmit || selectedTemplateId === null) return;
    createHero.mutate({ heroTemplateId: selectedTemplateId, name: trimmedName });
  }

  return (
    <div className="flex h-dvh flex-col bg-bg-base" style={{ paddingTop: "var(--safe-top)" }}>
      <div className="px-4 pb-2 pt-5 text-center">
        <h1 className="font-display text-xl font-semibold text-ink">Создайте героя</h1>
        <p className="mt-1 text-[12.5px] text-ink-mute">Выберите облик и дайте герою имя — так вас увидят другие игроки.</p>
      </div>

      <div className="flex-1 overflow-y-auto px-4 pb-4">
        {templates.isPending && (
          <div className="grid grid-cols-2 gap-2.5">
            {Array.from({ length: 4 }).map((_, i) => (
              <Skeleton key={i} className="aspect-[3/4] rounded-lg" />
            ))}
          </div>
        )}

        {templates.isError && <ErrorState error={templates.error} onRetry={() => templates.refetch()} />}

        {templates.data && (
          <div className="grid grid-cols-2 gap-2.5">
            {templates.data.map((template) => (
              <TemplateCard
                key={template.id}
                template={template}
                selected={selectedTemplateId === template.id}
                onSelect={() => setSelectedTemplateId(template.id)}
              />
            ))}
          </div>
        )}
      </div>

      <div className="flex flex-col gap-2.5 border-t border-hairline bg-bg-surface px-4 pb-[calc(var(--safe-bottom)+16px)] pt-3.5">
        <div>
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            maxLength={NAME_MAX_LENGTH}
            placeholder="Имя героя"
            className="w-full rounded-md border border-hairline bg-bg-raised px-3.5 py-2.5 font-body text-[14px] text-ink outline-none placeholder:text-ink-dim focus:border-ember"
          />
          {name.length > 0 && !nameValid && (
            <p className="mt-1 px-0.5 text-[11px] text-crimson">
              Имя должно быть от {NAME_MIN_LENGTH} до {NAME_MAX_LENGTH} символов.
            </p>
          )}
        </div>

        {createHero.isError && (
          <p className="px-0.5 text-[11px] text-crimson">Не удалось создать героя. Попробуйте ещё раз.</p>
        )}

        <Button onClick={handleSubmit} disabled={!canSubmit}>
          {createHero.isPending ? "Создаём…" : "Начать приключение"}
        </Button>
      </div>
    </div>
  );
}
