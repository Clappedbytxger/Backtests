/**
 * Lightweight, dependency-free line-icon set (stroke = currentColor) used by the
 * onboarding tour and the Academy. Replaces emoji with a consistent, professional
 * 24×24 stroke style so the product reads as finance-grade rather than playful.
 */

import type { SVGProps } from "react";

type IconProps = SVGProps<SVGSVGElement> & { className?: string };

const base = {
  viewBox: "0 0 24 24",
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 1.6,
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
};

/** Orientation / getting started. */
export function IconCompass({ className, ...p }: IconProps) {
  return (
    <svg {...base} className={className} {...p}>
      <circle cx="12" cy="12" r="9" />
      <polygon points="15.6,8.4 10.5,10.5 8.4,15.6 13.5,13.5" />
    </svg>
  );
}

/** Market regime / weather radar (concentric dome + ping). */
export function IconRadar({ className, ...p }: IconProps) {
  return (
    <svg {...base} className={className} {...p}>
      <path d="M3 18a9 9 0 0 1 18 0" />
      <path d="M7 18a5 5 0 0 1 10 0" />
      <line x1="3" y1="18" x2="21" y2="18" />
      <circle cx="12" cy="18" r="0.9" fill="currentColor" stroke="none" />
    </svg>
  );
}

/** Institutional positioning (crosshair = where the big capital aims). */
export function IconTarget({ className, ...p }: IconProps) {
  return (
    <svg {...base} className={className} {...p}>
      <circle cx="12" cy="12" r="8" />
      <circle cx="12" cy="12" r="3.4" />
      <line x1="12" y1="2.5" x2="12" y2="6" />
      <line x1="12" y1="18" x2="12" y2="21.5" />
      <line x1="2.5" y1="12" x2="6" y2="12" />
      <line x1="18" y1="12" x2="21.5" y2="12" />
    </svg>
  );
}

/** Backtest / equity curve. */
export function IconChart({ className, ...p }: IconProps) {
  return (
    <svg {...base} className={className} {...p}>
      <path d="M4 4v16h16" />
      <path d="M7 15l3-4 3 2 4-7" />
    </svg>
  );
}

/** Completion. */
export function IconCheckCircle({ className, ...p }: IconProps) {
  return (
    <svg {...base} className={className} {...p}>
      <circle cx="12" cy="12" r="9" />
      <path d="M8.4 12.4l2.5 2.5 4.7-5.3" />
    </svg>
  );
}

/** Observation (Academy stage 1). */
export function IconEye({ className, ...p }: IconProps) {
  return (
    <svg {...base} className={className} {...p}>
      <path d="M2.5 12s3.6-6 9.5-6 9.5 6 9.5 6-3.6 6-9.5 6-9.5-6-9.5-6z" />
      <circle cx="12" cy="12" r="2.6" />
    </svg>
  );
}

/** Research / experimentation (Academy stage 2). */
export function IconBeaker({ className, ...p }: IconProps) {
  return (
    <svg {...base} className={className} {...p}>
      <path d="M9 3h6" />
      <path d="M10 3v6l-4.6 8.6A1.5 1.5 0 0 0 6.7 20h10.6a1.5 1.5 0 0 0 1.3-2.4L14 9V3" />
      <line x1="7.6" y1="14" x2="16.4" y2="14" />
    </svg>
  );
}

/** Code / quant development (Academy stage 3). */
export function IconCode({ className, ...p }: IconProps) {
  return (
    <svg {...base} className={className} {...p}>
      <path d="M8 7l-4 5 4 5" />
      <path d="M16 7l4 5-4 5" />
      <line x1="13.6" y1="5" x2="10.4" y2="19" />
    </svg>
  );
}

/** Locked behind Developer mode. */
export function IconLock({ className, ...p }: IconProps) {
  return (
    <svg {...base} className={className} {...p}>
      <rect x="5" y="11" width="14" height="9" rx="2" />
      <path d="M8 11V8a4 4 0 0 1 8 0v3" />
    </svg>
  );
}
