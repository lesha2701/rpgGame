import { usePreferencesStore } from "@/store/preferencesStore";

/** Minimal window.Telegram.WebApp surface — only what this app actually
 * calls. Architecturally the same shape as the football frontend's own
 * lib/telegram.ts (read initData, ready/expand, safe areas, back button),
 * not copied — trimmed to Phase 1's real needs (auth header, viewport,
 * back navigation) rather than porting its full payments/haptics surface
 * up front. */

interface TelegramWebApp {
  initData: string;
  colorScheme: "light" | "dark";
  viewportHeight: number;
  isExpanded: boolean;
  ready: () => void;
  expand: () => void;
  disableVerticalSwipes?: () => void;
  BackButton?: {
    show: () => void;
    hide: () => void;
    onClick: (cb: () => void) => void;
    offClick: (cb: () => void) => void;
  };
  HapticFeedback?: {
    impactOccurred: (style: "light" | "medium" | "heavy" | "rigid" | "soft") => void;
    notificationOccurred: (type: "error" | "success" | "warning") => void;
  };
}

declare global {
  interface Window {
    Telegram?: { WebApp?: TelegramWebApp };
  }
}

export function getTelegramWebApp(): TelegramWebApp | null {
  return window.Telegram?.WebApp ?? null;
}

export function isInsideTelegram(): boolean {
  return Boolean(getTelegramWebApp()?.initData);
}

export function getRawInitData(): string {
  return getTelegramWebApp()?.initData ?? "";
}

export function initTelegramApp(): void {
  const webApp = getTelegramWebApp();
  if (!webApp) return;
  webApp.ready();
  webApp.expand();
  webApp.disableVerticalSwipes?.();
}

export function haptic(style: "light" | "medium" | "heavy" = "light"): void {
  if (!usePreferencesStore.getState().hapticsEnabled) return;
  getTelegramWebApp()?.HapticFeedback?.impactOccurred(style);
}

export function useTelegramBackButton(onBack: (() => void) | null): void {
  const webApp = getTelegramWebApp();
  if (!webApp?.BackButton) return;
  if (onBack) {
    webApp.BackButton.show();
    webApp.BackButton.onClick(onBack);
  } else {
    webApp.BackButton.hide();
  }
}
