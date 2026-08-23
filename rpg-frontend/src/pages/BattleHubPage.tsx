import { Link } from "react-router-dom";

import { AppIconArt } from "@/components/artwork";
import { BalanceBar } from "@/components/layout/BalanceBar";
import { findAppIconPath, useAppIcons } from "@/hooks/useAppIcons";

const MODES = [
  { to: "/campaign", key: "mode_campaign", title: "Кампания", description: "Сюжетный путь через регионы, элитных врагов и боссов." },
  { to: "/arena", key: "mode_arena", title: "Арена", description: "PvP-поединки с другими игроками." },
];

const MINIGAMES = [
  { to: "/battle/memory", key: "minigame_memory", title: "Запомни последовательность", description: "Повторите последовательность карт по памяти." },
  { to: "/battle/pairs", key: "minigame_pairs", title: "Найди пару", description: "Найдите одинаковые пары карт на скорость." },
  { to: "/battle/dummy", key: "minigame_dummy", title: "Боевой манекен", description: "Потренируйте атаку на неподвижной цели." },
  { to: "/battle/alchemy", key: "minigame_alchemy", title: "Алхимия", description: "Смешивайте зелья и получайте награды." },
  { to: "/battle/dice", key: "minigame_dice", title: "Тавернные кости", description: "Испытайте удачу в игре в кости на монеты." },
  { to: "/battle/cups", key: "minigame_cups", title: "Три кубка", description: "Угадайте, под каким кубком приз." },
];

/** Every combat-adjacent mode (Campaign, Arena, mini-games) lives under
 * one tab instead of Arena being buried in "Ещё". Both lists use the same
 * row shape — admin-uploaded image on the left, title+description on the
 * right (mirroring Expeditions' card, just laid out horizontally instead
 * of stacked) — no emoji anywhere; an icon with nothing uploaded yet
 * simply renders ArtFrame's empty-state wash. The mini-games list is
 * deliberately open-ended (MinigameType's own docstring flags this) — six
 * exist now, more can be added here later without restructuring
 * anything else. */
export function BattleHubPage() {
  const icons = useAppIcons();

  return (
    <div>
      <BalanceBar />
      <div className="flex flex-col gap-2.5 px-4 pb-2">
        {MODES.map((mode) => (
          <Link
            key={mode.to}
            to={mode.to}
            className="flex items-center gap-3 rounded-lg border border-hairline bg-bg-surface p-3.5 transition-colors active:bg-bg-raised"
          >
            <AppIconArt
              imagePath={findAppIconPath(icons.data, mode.key)}
              alt={mode.title}
              size="thumbnail"
              variant="ember"
              className="w-14 flex-none"
            />
            <div className="flex-1">
              <p className="font-display text-[15px] font-semibold text-ink">{mode.title}</p>
              <p className="mt-0.5 font-mono text-[10.5px] text-ink-dim">{mode.description}</p>
            </div>
            <span className="text-ink-dim">›</span>
          </Link>
        ))}
      </div>

      <p className="px-4 pb-2 pt-3 font-mono text-[10px] uppercase tracking-wide text-ink-dim">Мини-игры</p>
      <div className="flex flex-col gap-2.5 px-4 pb-6">
        {MINIGAMES.map((game) => (
          <Link
            key={game.to}
            to={game.to}
            className="flex items-center gap-3 rounded-lg border border-hairline bg-bg-surface p-3.5 transition-colors active:bg-bg-raised"
          >
            <AppIconArt
              imagePath={findAppIconPath(icons.data, game.key)}
              alt={game.title}
              size="thumbnail"
              variant="epic-wash"
              className="w-14 flex-none"
            />
            <div className="flex-1">
              <p className="font-display text-[15px] font-semibold text-ink">{game.title}</p>
              <p className="mt-0.5 font-mono text-[10.5px] text-ink-dim">{game.description}</p>
            </div>
            <span className="text-ink-dim">›</span>
          </Link>
        ))}
      </div>
    </div>
  );
}
