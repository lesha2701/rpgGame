import type { Rarity } from "@/types";

/** Visual treatment per rarity — deliberately more than a color swap (per
 * Ember & Iron's design brief: "не полагаться только на цвет"). Common is a
 * plain hairline; rare adds a glow; epic adds corner brackets; legendary adds
 * brackets + a breathing glow animation. */
export const RARITY_RING_CLASS: Record<Rarity, string> = {
  common: "ring-1 ring-hairline",
  rare: "ring-1 ring-rarity-rare/50 shadow-glow-rare",
  epic: "ring-1 ring-rarity-epic/55 shadow-glow-epic",
  legendary: "ring-1 ring-rarity-legendary/60 shadow-glow-legendary animate-legendary-breathe",
};

export const RARITY_LABEL: Record<Rarity, string> = {
  common: "Обычная",
  rare: "Редкая",
  epic: "Эпическая",
  legendary: "Легендарная",
};

export const RARITY_TEXT_CLASS: Record<Rarity, string> = {
  common: "text-rarity-common",
  rare: "text-rarity-rare",
  epic: "text-rarity-epic",
  legendary: "text-rarity-legendary",
};

export const RARITY_HAS_CORNERS: Record<Rarity, boolean> = {
  common: false,
  rare: false,
  epic: true,
  legendary: true,
};
