export interface BattleLogEntryOut {
  turn: number;
  attacker: string;
  target: string;
  action_type: string;
  skill_id: number | null;
  damage: number;
  critical: boolean;
  target_hp_after: number;
  status_effects: Record<string, unknown>[];
}

export interface EnemySummaryOut {
  id: number;
  name: string;
  level: number;
}

export interface BattleOut {
  id: number;
  enemy: EnemySummaryOut;
  result: "won" | "lost";
  turns: number;
  log: BattleLogEntryOut[];
  reward_xp: number;
  reward_coins: number;
  hero_level: number;
  hero_xp: number;
  balance: number;
  created_at: string;
}

export interface StartBattleRequest {
  enemy_template_id: number;
  idempotency_key?: string | null;
}
