import { NavLink } from "react-router-dom";

import { AppIconArt } from "@/components/artwork";
import { findAppIconPath, useAppIcons } from "@/hooks/useAppIcons";

const ITEMS = [
  { to: "/chests", label: "Сундуки", key: "nav_chests", end: true },
  { to: "/battle", label: "Битвы", key: "nav_battle", end: false },
  { to: "/hero", label: "Герой", key: "nav_hero", end: false },
  { to: "/inventory", label: "Инвентарь", key: "nav_inventory", end: false },
  { to: "/more", label: "Ещё", key: "nav_more", end: false },
] as const;

export function BottomNav() {
  const icons = useAppIcons();

  return (
    <nav
      className="flex gap-0.5 border-t border-hairline bg-bg-surface/95 px-1.5 pt-1.5 backdrop-blur-sm"
      style={{ paddingBottom: "calc(6px + var(--safe-bottom))" }}
    >
      {ITEMS.map((item) => (
        <NavLink
          key={item.to}
          to={item.to}
          end={item.end}
          className={({ isActive }) =>
            `flex flex-1 flex-col items-center gap-1 rounded-lg py-1.5 transition-colors ${
              isActive ? "bg-ember/10" : ""
            }`
          }
        >
          {({ isActive }) => (
            <>
              <AppIconArt
                imagePath={findAppIconPath(icons.data, item.key)}
                alt={item.label}
                size="thumbnail"
                className={`h-5 w-5 !rounded-md transition-opacity ${isActive ? "opacity-100" : "opacity-55"}`}
              />
              <span className={`font-mono text-[9px] ${isActive ? "font-bold text-ember-bright" : "text-ink-dim"}`}>
                {item.label}
              </span>
            </>
          )}
        </NavLink>
      ))}
    </nav>
  );
}
