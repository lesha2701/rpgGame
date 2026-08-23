import { ApiRequestError } from "@/services/api";
import { Button } from "./Button";

/** Maps the backend's {error:{code,message}} envelope to user-facing copy.
 * Falls back to a generic message for anything not explicitly handled
 * rather than ever surfacing a raw error/stack trace. */
function messageFor(error: unknown): string {
  if (error instanceof ApiRequestError) {
    if (error.code === "network_error") return "Не удалось связаться с сервером. Проверьте соединение.";
    if (error.status === 401) return "Сессия истекла. Перезайдите в приложение.";
    if (error.status === 404) return "Не найдено.";
    if (error.status === 409) return "Действие уже выполнено или конфликтует с текущим состоянием.";
    return error.message || "Что-то пошло не так.";
  }
  return "Что-то пошло не так.";
}

export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  return (
    <div className="flex flex-col items-center gap-3 rounded-lg border border-crimson/30 bg-bg-surface px-6 py-10 text-center">
      <span className="text-2xl opacity-60" aria-hidden>
        ⚠
      </span>
      <p className="max-w-[32ch] text-[13px] leading-relaxed text-ink-mute">{messageFor(error)}</p>
      {onRetry && (
        <Button variant="secondary" onClick={onRetry}>
          Повторить
        </Button>
      )}
    </div>
  );
}
