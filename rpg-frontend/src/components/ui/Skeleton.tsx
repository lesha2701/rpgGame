export function Skeleton({ className = "" }: { className?: string }) {
  return (
    <div
      className={`animate-shimmer rounded-md bg-bg-raised bg-[linear-gradient(90deg,transparent,rgba(243,237,228,0.06),transparent)] bg-[length:400px_100%] ${className}`}
    />
  );
}
