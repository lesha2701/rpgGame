import type { ReactNode } from "react";
import { Link } from "react-router-dom";

import { ScreenHeader } from "@/components/layout/ScreenHeader";
import { ErrorState, Skeleton } from "@/components/ui";
import { useSession } from "@/hooks/useSession";
import { usePreferencesStore } from "@/store/preferencesStore";
import { useAuthStore } from "@/store/authStore";

function Toggle({ checked, onChange }: { checked: boolean; onChange: (v: boolean) => void }) {
  return (
    <button
      role="switch"
      aria-checked={checked}
      onClick={() => onChange(!checked)}
      className={`h-6 w-11 flex-none rounded-full transition-colors ${checked ? "bg-ember" : "bg-bg-raised"}`}
    >
      <span
        className={`block h-5 w-5 translate-y-0.5 rounded-full bg-ink transition-transform ${
          checked ? "translate-x-[22px]" : "translate-x-0.5"
        }`}
      />
    </button>
  );
}

function Row({ label, description, children }: { label: string; description?: string; children: ReactNode }) {
  return (
    <div className="flex items-center gap-3 rounded-lg border border-hairline bg-bg-surface px-3.5 py-3">
      <div className="flex-1">
        <p className="text-[13px] font-bold text-ink">{label}</p>
        {description && <p className="mt-0.5 text-[11px] text-ink-dim">{description}</p>}
      </div>
      {children}
    </div>
  );
}

export function SettingsPage() {
  const session = useSession();
  const adminToken = useAuthStore((s) => s.adminToken);
  const hapticsEnabled = usePreferencesStore((s) => s.hapticsEnabled);
  const setHapticsEnabled = usePreferencesStore((s) => s.setHapticsEnabled);

  return (
    <div className="pb-6">
      <ScreenHeader title="Настройки" />
      <div className="flex flex-col gap-4 px-4">
        <section>
          <p className="mb-2 font-mono text-[10px] uppercase tracking-wide text-ink-dim">Аккаунт</p>
          {session.isPending && <Skeleton className="h-16" />}
          {session.isError && <ErrorState error={session.error} onRetry={() => session.refetch()} />}
          {session.data && (
            <div className="rounded-lg border border-hairline bg-bg-surface px-3.5 py-3">
              <p className="text-[13px] font-bold text-ink">
                {session.data.user.first_name ?? session.data.user.username ?? `Игрок #${session.data.user.id}`}
              </p>
              <p className="mt-1 font-mono text-[11px] text-ink-dim">Telegram ID: {session.data.user.telegram_id}</p>
              <p className="mt-0.5 font-mono text-[11px] text-ink-dim">
                Реферальный код: {session.data.user.referral_code} · приглашено {session.data.user.referral_count}
              </p>
            </div>
          )}
        </section>

        <section>
          <p className="mb-2 font-mono text-[10px] uppercase tracking-wide text-ink-dim">Предпочтения</p>
          <Row label="Вибро-отклик" description="Тактильная обратная связь Telegram при действиях">
            <Toggle checked={hapticsEnabled} onChange={setHapticsEnabled} />
          </Row>
        </section>

        {adminToken && (
          <section>
            <p className="mb-2 font-mono text-[10px] uppercase tracking-wide text-ink-dim">Администрирование</p>
            <Link
              to="/admin"
              className="flex items-center justify-between rounded-lg border border-ember/40 bg-ember/10 px-3.5 py-3"
            >
              <span className="text-[13px] font-bold text-ember-bright">Открыть админ-панель</span>
              <span className="text-ember-bright">→</span>
            </Link>
          </section>
        )}

        <section>
          <p className="mb-2 font-mono text-[10px] uppercase tracking-wide text-ink-dim">О приложении</p>
          <div className="rounded-lg border border-hairline bg-bg-surface px-3.5 py-3 font-mono text-[11px] text-ink-dim">
            rpg-frontend v0.1.0
          </div>
        </section>
      </div>
    </div>
  );
}
