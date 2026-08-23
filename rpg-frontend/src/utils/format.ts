export function formatNumber(value: number): string {
  return value.toLocaleString("ru-RU");
}

const RACE_CLASS_LABEL = (race: string, cls: string) => `${race} · ${cls}`;

export function heroTagline(raceName: string, className: string): string {
  return RACE_CLASS_LABEL(raceName, className);
}
