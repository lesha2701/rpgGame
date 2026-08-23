import type { HeroProgressOut } from "./common";

export interface MemoryStartOut {
  attempt_id: number;
  sequence: number[];
  symbols: string[];
}

export interface PairsStartOut {
  attempt_id: number;
  layout: number[];
  symbols: string[];
}

export interface MinigameResultOut {
  success: boolean;
  reward_xp: number;
  reward_coins: number;
  daily_rewarded_remaining: number;
  hero_progress: HeroProgressOut;
}

export interface DummyStartOut {
  attempt_id: number;
  directions: string[];
}

export interface AlchemyStartOut {
  attempt_id: number;
  recipe: number[];
  ingredients: string[];
}

export interface DiceRoundOut {
  attempt_id: number;
  roll: number | null;
  busted: boolean;
  pot: number;
  rolls_made: number;
  max_rolls: number;
  finished: boolean;
  reward_xp: number;
  reward_coins: number;
  daily_rewarded_remaining: number;
  hero_progress: HeroProgressOut;
}

export interface CupsRoundOut {
  attempt_id: number;
  correct: boolean | null;
  round: number;
  max_rounds: number;
  finished: boolean;
  reward_xp: number;
  reward_coins: number;
  daily_rewarded_remaining: number;
  hero_progress: HeroProgressOut;
}
