import type { UserMeOut } from "./user";

export interface BattleStatsOut {
  played: number;
  wins: number;
  losses: number;
}

export interface ArenaStatsOut {
  played: number;
  wins: number;
  losses: number;
}

export interface ExpeditionStatsOut {
  started: number;
  claimed: number;
}

export interface QuestStatsOut {
  claimed: number;
}

export interface ChestStatsOut {
  opened: number;
}

export interface ReferralStatsOut {
  referral_count: number;
  successful_referrals: number;
}

export interface CampaignStatsOut {
  nodes_cleared: number;
  total_clears: number;
}

export interface HeroActivityStatsOut {
  items_equipped: number;
  skills_upgraded: number;
}

export interface ProfileStatisticsOut {
  battles: BattleStatsOut;
  arena: ArenaStatsOut;
  campaign: CampaignStatsOut;
  expeditions: ExpeditionStatsOut;
  quests: QuestStatsOut;
  chests: ChestStatsOut;
  referrals: ReferralStatsOut;
  hero_activity: HeroActivityStatsOut;
}

export interface ProfileOut {
  user: UserMeOut;
  balance: number;
  statistics: ProfileStatisticsOut;
}

export interface PublicHeroOut {
  name: string;
  level: number;
  race: string;
  character_class: string;
}

export interface PublicStatisticsOut {
  arena_wins: number;
  pve_wins: number;
  campaign_nodes_cleared: number;
  expeditions_claimed: number;
  quests_claimed: number;
  chests_opened: number;
}

export interface PublicProfileOut {
  user_id: number;
  username: string | null;
  hero: PublicHeroOut | null;
  statistics: PublicStatisticsOut;
}
