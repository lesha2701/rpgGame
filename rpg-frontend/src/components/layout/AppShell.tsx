import { Outlet } from "react-router-dom";

import { BottomNav } from "./BottomNav";
import { SessionGate } from "./SessionGate";

/** Telegram Mini App shell: fills the viewport, respects safe-area insets
 * (defined once in styles/theme.css), keeps the bottom nav pinned below
 * scrollable page content. Mobile-first — the same layout holds up at
 * desktop widths by simply staying centered/narrow rather than switching to
 * a different (dashboard-style) composition. */
export function AppShell() {
  return (
    <SessionGate>
      <div className="mx-auto flex h-full max-w-md flex-col bg-bg-base">
        <main className="flex-1 overflow-y-auto" style={{ paddingTop: "var(--safe-top)" }}>
          <Outlet />
        </main>
        <BottomNav />
      </div>
    </SessionGate>
  );
}
