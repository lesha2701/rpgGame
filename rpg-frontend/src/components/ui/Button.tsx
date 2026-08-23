import type { ButtonHTMLAttributes } from "react";

export type ButtonVariant = "primary" | "secondary" | "ghost" | "frost";

export const BUTTON_VARIANT_CLASS: Record<ButtonVariant, string> = {
  primary: "bg-gradient-to-b from-ember-bright to-ember text-[#1D1204] shadow-glow-ember",
  secondary: "bg-bg-raised text-ink border border-hairline",
  ghost: "bg-transparent text-ink-mute border border-hairline",
  frost: "bg-gradient-to-b from-iron-teal-bright to-iron-teal text-[#0C1512]",
};

export const BUTTON_BASE_CLASS =
  "rounded-md px-4 py-2.5 font-body text-[13px] font-bold transition-opacity active:opacity-80 disabled:cursor-not-allowed disabled:opacity-40 text-center";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
}

export function Button({ variant = "primary", className = "", ...props }: ButtonProps) {
  return <button className={`${BUTTON_BASE_CLASS} ${BUTTON_VARIANT_CLASS[variant]} ${className}`} {...props} />;
}
