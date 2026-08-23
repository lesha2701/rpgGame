import type { ReactNode } from "react";

export function Pill({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    <div
      className={`inline-flex items-center gap-1.5 rounded-full border border-ink/10 bg-bg-base/55 px-3 py-1.5 font-mono text-[11.5px] text-ink backdrop-blur-sm ${className}`}
    >
      {children}
    </div>
  );
}
