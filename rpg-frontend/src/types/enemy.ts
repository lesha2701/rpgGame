export interface EnemyOut {
  id: number;
  name: string;
  description: string | null;
  image_path: string | null;
  level: number;
  hp: number;
  attack: number;
  defense: number;
  speed: number;
  crit_chance: number;
  crit_damage: number;
  reward_xp: number;
  reward_coins: number;
  is_available_to_user: boolean;
}
