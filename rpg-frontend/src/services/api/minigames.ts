import { api } from "./client";
import type {
  AlchemyStartOut,
  CupsRoundOut,
  DiceRoundOut,
  DummyStartOut,
  MemoryStartOut,
  MinigameResultOut,
  PairsStartOut,
} from "@/types";

export async function startMemory(): Promise<MemoryStartOut> {
  const { data } = await api.post<MemoryStartOut>("/minigames/memory/start");
  return data;
}

export async function submitMemory(attemptId: number, answer: number[]): Promise<MinigameResultOut> {
  const { data } = await api.post<MinigameResultOut>(`/minigames/memory/${attemptId}/submit`, { answer });
  return data;
}

export async function startPairs(): Promise<PairsStartOut> {
  const { data } = await api.post<PairsStartOut>("/minigames/pairs/start");
  return data;
}

export async function completePairs(attemptId: number, moves: number): Promise<MinigameResultOut> {
  const { data } = await api.post<MinigameResultOut>(`/minigames/pairs/${attemptId}/complete`, { moves });
  return data;
}

export async function startDummy(): Promise<DummyStartOut> {
  const { data } = await api.post<DummyStartOut>("/minigames/dummy/start");
  return data;
}

export async function completeDummy(attemptId: number, hits: number): Promise<MinigameResultOut> {
  const { data } = await api.post<MinigameResultOut>(`/minigames/dummy/${attemptId}/complete`, { hits });
  return data;
}

export async function startAlchemy(): Promise<AlchemyStartOut> {
  const { data } = await api.post<AlchemyStartOut>("/minigames/alchemy/start");
  return data;
}

export async function submitAlchemy(attemptId: number, answer: number[]): Promise<MinigameResultOut> {
  const { data } = await api.post<MinigameResultOut>(`/minigames/alchemy/${attemptId}/submit`, { answer });
  return data;
}

export async function startDice(): Promise<DiceRoundOut> {
  const { data } = await api.post<DiceRoundOut>("/minigames/dice/start");
  return data;
}

export async function rollDice(attemptId: number): Promise<DiceRoundOut> {
  const { data } = await api.post<DiceRoundOut>(`/minigames/dice/${attemptId}/roll`);
  return data;
}

export async function bankDice(attemptId: number): Promise<DiceRoundOut> {
  const { data } = await api.post<DiceRoundOut>(`/minigames/dice/${attemptId}/bank`);
  return data;
}

export async function startCups(): Promise<CupsRoundOut> {
  const { data } = await api.post<CupsRoundOut>("/minigames/cups/start");
  return data;
}

export async function guessCups(attemptId: number, cup: number): Promise<CupsRoundOut> {
  const { data } = await api.post<CupsRoundOut>(`/minigames/cups/${attemptId}/guess`, { cup });
  return data;
}
