import { NavLink, Outlet } from "react-router-dom";

const NAV = [
  { to: "/admin", label: "Обзор", end: true },
  { to: "/admin/users", label: "Пользователи" },
  { to: "/admin/chests", label: "Сундуки" },
  { to: "/admin/catalog", label: "Каталог" },
  { to: "/admin/app-icons", label: "Иконки" },
];

export function AdminLayout() {
  return (
    <div className="min-h-dvh bg-bg-base">
      <header className="flex flex-wrap items-center justify-between gap-3 border-b border-hairline bg-bg-surface px-5 py-3">
        <div className="flex items-center gap-4">
          <span className="font-display text-lg font-semibold text-ink">Админ-панель</span>
          <nav className="flex gap-1">
            {NAV.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                className={({ isActive }) =>
                  `rounded-md px-3 py-1.5 font-mono text-[11.5px] font-bold ${
                    isActive ? "bg-ember/15 text-ember-bright" : "text-ink-mute"
                  }`
                }
              >
                {item.label}
              </NavLink>
            ))}
          </nav>
        </div>
        <NavLink to="/" className="font-mono text-[11px] text-ink-dim">
          ← в игру
        </NavLink>
      </header>
      <main className="mx-auto max-w-4xl px-5 py-6">
        <Outlet />
      </main>
    </div>
  );
}
