import { Link } from "react-router-dom";

import { RESOURCES } from "@/admin/resources";
import { useAdminChests } from "@/hooks/useAdminChests";
import { useUserStats } from "@/hooks/useAdminUsers";

function StatCard({ label, value, to }: { label: string; value: string; to: string }) {
  return (
    <Link to={to} className="rounded-lg border border-hairline bg-bg-surface p-4 hover:border-ember/50">
      <p className="font-mono text-[10px] uppercase tracking-wide text-ink-dim">{label}</p>
      <p className="mt-1 font-display text-2xl font-semibold text-ink">{value}</p>
    </Link>
  );
}

export function AdminDashboardPage() {
  const userStats = useUserStats();
  const chests = useAdminChests();
  const races = RESOURCES.races.hooks.useList();
  const classes = RESOURCES.classes.hooks.useList();
  const heroTemplates = RESOURCES["hero-templates"].hooks.useList();
  const enemies = RESOURCES.enemies.hooks.useList();
  const items = RESOURCES.items.hooks.useList();
  const expeditions = RESOURCES.expeditions.hooks.useList();
  const quests = RESOURCES.quests.hooks.useList();

  return (
    <div>
      <h1 className="mb-1 font-display text-2xl font-semibold text-ink">Обзор</h1>
      <p className="mb-6 text-[13px] text-ink-mute">
        Управление игрой. Пользователи, сундуки, расы, классы, шаблоны героев, враги, предметы, экспедиции и квесты
        — всё редактируемо; изображения для героев/врагов/предметов/экспедиций можно загрузить прямо из формы
        редактирования.
      </p>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <StatCard label="Пользователи" value={userStats.data ? String(userStats.data.total_users) : "…"} to="/admin/users" />
        <StatCard label="Сундуки" value={chests.data ? String(chests.data.length) : "…"} to="/admin/chests" />
        <StatCard label="Расы" value={races.data ? String(races.data.length) : "…"} to="/admin/catalog/races" />
        <StatCard label="Классы" value={classes.data ? String(classes.data.length) : "…"} to="/admin/catalog/classes" />
        <StatCard
          label="Шаблоны героев"
          value={heroTemplates.data ? String(heroTemplates.data.length) : "…"}
          to="/admin/catalog/hero-templates"
        />
        <StatCard label="Враги" value={enemies.data ? String(enemies.data.length) : "…"} to="/admin/catalog/enemies" />
        <StatCard label="Предметы" value={items.data ? String(items.data.length) : "…"} to="/admin/catalog/items" />
        <StatCard
          label="Экспедиции"
          value={expeditions.data ? String(expeditions.data.length) : "…"}
          to="/admin/catalog/expeditions"
        />
        <StatCard label="Квесты" value={quests.data ? String(quests.data.length) : "…"} to="/admin/catalog/quests" />
      </div>

      <div className="mt-8 rounded-lg border border-dashed border-hairline bg-bg-surface p-4">
        <p className="mb-2 font-mono text-[11px] font-bold text-ink">Чего всё ещё нет на backend</p>
        <ul className="list-disc pl-5 text-[12px] leading-relaxed text-ink-mute">
          <li>Жёсткого удаления — как и у сундуков, деактивация (вкл/выкл) им и является.</li>
          <li>Изменения размера/обрезки загруженных изображений, CDN, S3 — только локальный диск.</li>
          <li>Журнала admin-действий (audit log) — кто и когда что изменил, нигде не пишется.</li>
        </ul>
        <p className="mt-2 text-[11px] text-ink-dim">Ничего из этого не подделано — см. FRONTEND_API_MAP.md.</p>
      </div>
    </div>
  );
}
