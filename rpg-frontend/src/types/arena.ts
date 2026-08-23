import type { BattleLogEntryOut } from "./battle";

export interface ArenaParticipantOut {
  user_id: number;
  hero_id: number;
  hero_name: string;
  current_hp: number;
  max_hp: number;
  has_acted_this_round: boolean;
}

export interface ArenaMatchOut {
  id: number;
  status: "running" | "finished";
  current_round: number;
  round_deadline_at: string;
  player_a: ArenaParticipantOut;
  player_b: ArenaParticipantOut;
  log: BattleLogEntryOut[];
  winner_user_id: number | null;
  reward_xp: number;
  reward_coins: number;
  created_at: string;
  finished_at: string | null;
}

export interface StartArenaMatchRequest {
  opponent_user_id: number;
}

export interface ArenaActionRequest {
  round: number;
  action_type: "basic_attack" | "skill";
  skill_id?: number | null;
}
