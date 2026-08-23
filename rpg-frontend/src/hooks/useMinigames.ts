import { useMutation, useQueryClient } from "@tanstack/react-query";

import { minigamesApi } from "@/services/api";

function useInvalidateAfterMinigame() {
  const queryClient = useQueryClient();
  return () => {
    queryClient.invalidateQueries({ queryKey: ["session"] });
    queryClient.invalidateQueries({ queryKey: ["profile"] });
  };
}

export function useStartMemory() {
  return useMutation({ mutationFn: minigamesApi.startMemory });
}

export function useSubmitMemory() {
  const invalidate = useInvalidateAfterMinigame();
  return useMutation({
    mutationFn: ({ attemptId, answer }: { attemptId: number; answer: number[] }) =>
      minigamesApi.submitMemory(attemptId, answer),
    onSuccess: invalidate,
  });
}

export function useStartPairs() {
  return useMutation({ mutationFn: minigamesApi.startPairs });
}

export function useCompletePairs() {
  const invalidate = useInvalidateAfterMinigame();
  return useMutation({
    mutationFn: ({ attemptId, moves }: { attemptId: number; moves: number }) =>
      minigamesApi.completePairs(attemptId, moves),
    onSuccess: invalidate,
  });
}

export function useStartDummy() {
  return useMutation({ mutationFn: minigamesApi.startDummy });
}

export function useCompleteDummy() {
  const invalidate = useInvalidateAfterMinigame();
  return useMutation({
    mutationFn: ({ attemptId, hits }: { attemptId: number; hits: number }) =>
      minigamesApi.completeDummy(attemptId, hits),
    onSuccess: invalidate,
  });
}

export function useStartAlchemy() {
  return useMutation({ mutationFn: minigamesApi.startAlchemy });
}

export function useSubmitAlchemy() {
  const invalidate = useInvalidateAfterMinigame();
  return useMutation({
    mutationFn: ({ attemptId, answer }: { attemptId: number; answer: number[] }) =>
      minigamesApi.submitAlchemy(attemptId, answer),
    onSuccess: invalidate,
  });
}

export function useStartDice() {
  return useMutation({ mutationFn: minigamesApi.startDice });
}

export function useRollDice() {
  const invalidate = useInvalidateAfterMinigame();
  return useMutation({
    mutationFn: (attemptId: number) => minigamesApi.rollDice(attemptId),
    onSuccess: (res) => {
      if (res.finished) invalidate();
    },
  });
}

export function useBankDice() {
  const invalidate = useInvalidateAfterMinigame();
  return useMutation({
    mutationFn: (attemptId: number) => minigamesApi.bankDice(attemptId),
    onSuccess: invalidate,
  });
}

export function useStartCups() {
  return useMutation({ mutationFn: minigamesApi.startCups });
}

export function useGuessCups() {
  const invalidate = useInvalidateAfterMinigame();
  return useMutation({
    mutationFn: ({ attemptId, cup }: { attemptId: number; cup: number }) => minigamesApi.guessCups(attemptId, cup),
    onSuccess: (res) => {
      if (res.finished) invalidate();
    },
  });
}
