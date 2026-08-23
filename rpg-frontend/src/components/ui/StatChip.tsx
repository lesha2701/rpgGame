export function StatChip({ value, label }: { value: string | number; label: string }) {
  return (
    <div className="flex-1 rounded-md border border-hairline bg-bg-raised/70 px-1 py-2 text-center backdrop-blur-sm">
      <span className="block font-mono text-[13px] font-bold text-ink">{value}</span>
      <span className="block font-mono text-[9px] uppercase tracking-wide text-ink-dim">{label}</span>
    </div>
  );
}
