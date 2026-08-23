import { create } from "zustand";

const STORAGE_KEY = "rpg.preferences.hapticsEnabled";

function readInitial(): boolean {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw === null ? true : raw === "true";
  } catch {
    return true;
  }
}

interface PreferencesState {
  hapticsEnabled: boolean;
  setHapticsEnabled: (enabled: boolean) => void;
}

/** Client-only preference — no backend field for this exists (or should
 * exist; it's not gameplay data). Persisted to localStorage directly rather
 * than pulling in a persistence middleware for one boolean. */
export const usePreferencesStore = create<PreferencesState>((set) => ({
  hapticsEnabled: readInitial(),
  setHapticsEnabled: (hapticsEnabled) => {
    try {
      localStorage.setItem(STORAGE_KEY, String(hapticsEnabled));
    } catch {
      // localStorage unavailable (e.g. private mode) — in-memory only, fine.
    }
    set({ hapticsEnabled });
  },
}));
