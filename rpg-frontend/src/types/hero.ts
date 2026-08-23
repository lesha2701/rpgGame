import type { HeroTemplateOut } from "./catalog";

export interface HeroStatsOut {
  hp: number;
  attack: number;
  defense: number;
  speed: number;
  crit_chance: number;
  crit_damage: number;
}

export interface UserHeroOut {
  id: number;
  level: number;
  xp: number;
  xp_to_next_level: number | null;
  /** 1..10, derived server-side from level (progression.visual_stage_for_level).
   * Never recompute this client-side — see FRONTEND_API_MAP.md. */
  visual_stage: number;
  hero_template: HeroTemplateOut;
  stats: HeroStatsOut;
}
