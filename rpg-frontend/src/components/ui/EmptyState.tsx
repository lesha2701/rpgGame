import type { ReactNode } from "react";

interface EmptyStateProps {
  icon?: string;
  title: string;
  description?: string;
  action?: ReactNode;
}

export function EmptyState({ icon = "○", title, description, action }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center gap-2 rounded-lg border border-dashed border-hairline bg-bg-surface px-6 py-10 text-center">
      <span className="text-2xl opacity-40" aria-hidden>
        {icon}
      </span>
      <p className="font-display text-base font-semibold text-ink">{title}</p>
      {description && <p className="max-w-[28ch] text-[12.5px] leading-relaxed text-ink-mute">{description}</p>}
      {action}
    </div>
  );
}
