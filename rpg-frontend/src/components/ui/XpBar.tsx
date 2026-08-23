interface XpBarProps {
  xp: number;
  xpToNextLevel: number | null;
  label?: string;
}

/** xp_to_next_level === null means the hero is at MAX_LEVEL (progression.py)
 * — render a full, capped bar rather than dividing by zero. */
export function XpBar({ xp, xpToNextLevel, label }: XpBarProps) {
  const isMaxed = xpToNextLevel === null;
  const total = isMaxed ? xp : xp + xpToNextLevel;
  const pct = isMaxed || total === 0 ? 100 : Math.min(100, Math.round((xp / total) * 100));

  return (
    <div>
      <div className="mb-1 flex justify-between font-mono text-[10px] text-ink-dim">
        <span>{label}</span>
        <span>{isMaxed ? "MAX" : `${xp.toLocaleString("ru-RU")} / ${total.toLocaleString("ru-RU")}`}</span>
      </div>
      <div className="h-1.5 overflow-hidden rounded-full bg-bg-raised">
        <div
          className="h-full rounded-full bg-gradient-to-r from-ember-deep to-ember-bright"
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}
