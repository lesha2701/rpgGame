import { useNavigate } from "react-router-dom";

export function ScreenHeader({ title }: { title: string }) {
  const navigate = useNavigate();
  return (
    <div className="flex items-center gap-3 px-4 py-3">
      <button
        onClick={() => navigate(-1)}
        className="rounded-full border border-hairline bg-bg-surface px-3 py-1.5 font-mono text-[12px] text-ink-mute"
        aria-label="Назад"
      >
        ←
      </button>
      <h1 className="font-display text-lg font-semibold text-ink">{title}</h1>
    </div>
  );
}
