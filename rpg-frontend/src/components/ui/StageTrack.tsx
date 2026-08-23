/** The 10-dot visual_stage indicator — `visualStage` must come straight from
 * UserHeroOut.visual_stage (server-computed), never recomputed here. */
export function StageTrack({ visualStage }: { visualStage: number }) {
  return (
    <div className="mb-3 flex gap-[3px]">
      {Array.from({ length: 10 }, (_, i) => i + 1).map((stage) => (
        <div
          key={stage}
          className={`h-[3px] flex-1 rounded-full ${stage <= visualStage ? "bg-ember" : "bg-hairline"}`}
        />
      ))}
    </div>
  );
}
