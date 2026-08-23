import { Link, type LinkProps } from "react-router-dom";

import { BUTTON_BASE_CLASS, BUTTON_VARIANT_CLASS, type ButtonVariant } from "./Button";

interface LinkButtonProps extends LinkProps {
  variant?: ButtonVariant;
  className?: string;
}

/** Button styled as a navigation link — kept separate from Button rather
 * than giving Button an `asChild` polymorphic prop, since that needs a
 * Slot primitive this project doesn't otherwise need. */
export function LinkButton({ variant = "primary", className = "", ...props }: LinkButtonProps) {
  return <Link className={`inline-block ${BUTTON_BASE_CLASS} ${BUTTON_VARIANT_CLASS[variant]} ${className}`} {...props} />;
}
