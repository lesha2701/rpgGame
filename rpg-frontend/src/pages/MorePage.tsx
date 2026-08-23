import { Link } from "react-router-dom";

import { AppIconArt } from "@/components/artwork";
import { BalanceBar } from "@/components/layout/BalanceBar";
import { findAppIconPath, useAppIcons } from "@/hooks/useAppIcons";

const SECTIONS = [
  { to: "/collection", key: "more_collection", label: "Коллекция", description: "Просмотр собранных героев и персонажей." },
  { to: "/bestiary", key: "more_bestiary", label: "Бестиарий", description: "Каталог врагов кампании и их характеристики." },
  { to: "/quests", key: "more_quests", label: "Квесты", description: "Активные задания и награды за их выполнение." },
  { to: "/expeditions", key: "more_expeditions", label: "Экспедиции", description: "Отправляйте героя за опытом и золотом." },
  { to: "/leaderboards", key: "more_leaderboards", label: "Лидерборды", description: "Рейтинги игроков по разным показателям." },
  { to: "/equipment", key: "more_equipment", label: "Экипировка", description: "Управление снаряжением героя." },
  { to: "/profile", key: "more_statistics", label: "Статистика", description: "Подробная игровая статистика и достижения." },
  { to: "/settings", key: "more_settings", label: "Настройки", description: "Параметры приложения и аккаунта." },
];

export function MorePage() {
  const icons = useAppIcons();

  return (
    <div>
      <BalanceBar />
      <div className="flex flex-col gap-2.5 px-4 pb-6">
        {SECTIONS.map((s) => (
          <Link
            key={s.to}
            to={s.to}
            className="flex items-center gap-3 rounded-lg border border-hairline bg-bg-surface p-3.5 transition-colors active:bg-bg-raised"
          >
            <AppIconArt
              imagePath={findAppIconPath(icons.data, s.key)}
              alt={s.label}
              size="thumbnail"
              variant="frost"
              className="w-14 flex-none"
            />
            <div className="flex-1">
              <p className="font-display text-[15px] font-semibold text-ink">{s.label}</p>
              <p className="mt-0.5 font-mono text-[10.5px] text-ink-dim">{s.description}</p>
            </div>
            <span className="text-ink-dim">›</span>
          </Link>
        ))}
      </div>
    </div>
  );
}
