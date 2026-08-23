import { ScreenHeader } from "./ScreenHeader";

interface StubScreenProps {
  title: string;
  phase: string;
  endpoints: string[];
}

/** Every screen from the approved Ember & Iron design is routed and
 * reachable — this is the honest "not wired to real data this pass" state
 * for the ones staged for Phase 2–4 (see FRONTEND_API_MAP.md), instead of
 * silently faking data or leaving a dead link. */
export function StubScreen({ title, phase, endpoints }: StubScreenProps) {
  return (
    <div>
      <ScreenHeader title={title} />
      <div className="mx-4 flex flex-col items-center gap-3 rounded-lg border border-dashed border-hairline bg-bg-surface px-6 py-12 text-center">
        <span className="text-2xl opacity-40" aria-hidden>
          🛠
        </span>
        <p className="font-display text-base font-semibold text-ink">Экран запланирован на {phase}</p>
        <p className="max-w-[34ch] text-[12.5px] leading-relaxed text-ink-mute">
          Визуальное направление подтверждено (Ember &amp; Iron v3); интеграция с backend ещё не подключена в этом
          проходе — см. <code className="font-mono text-ink">FRONTEND_API_MAP.md</code>.
        </p>
        {endpoints.length > 0 && (
          <div className="mt-1 flex flex-col gap-1">
            {endpoints.map((e) => (
              <code key={e} className="font-mono text-[10.5px] text-ink-dim">
                {e}
              </code>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
