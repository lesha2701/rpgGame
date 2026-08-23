/** Mirrors rpg-backend/app/services/progression.py's constants — NOT a
 * reimplementation of visual_stage_for_level (that value always comes from
 * the server, see UserHeroOut.visual_stage). This only derives the inverse
 * (which level unlocks each of the 10 stages), needed to label the
 * Progression path's locked stages — the same cadence the backend already
 * uses, not a new number invented on the frontend. */
const LEVELS_PER_TIER = 10;
const STAGE_COUNT = 10;

export interface StageInfo {
  stage: number;
  unlockLevel: number;
}

export function stagePath(): StageInfo[] {
  return Array.from({ length: STAGE_COUNT }, (_, i) => {
    const stage = i + 1;
    return { stage, unlockLevel: (stage - 1) * LEVELS_PER_TIER + 1 };
  });
}
