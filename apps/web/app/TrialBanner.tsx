"use client";

import { useLicense } from "@/lib/license";

/**
 * Unobtrusive top strip shown only during the active trial:
 * "Quant OS Pro Trial: Noch X Tage verbleibend".
 */
export default function TrialBanner() {
  const { status, daysRemaining, trialTotalDays } = useLicense();
  if (status !== "TRIAL") return null;

  const dayWord = daysRemaining === 1 ? "Tag" : "Tage";
  const urgent = daysRemaining <= 2;

  return (
    <div
      className={[
        "flex items-center justify-center gap-2 px-4 py-1.5 text-center text-xs font-medium",
        urgent
          ? "bg-amber-500/15 text-amber-300 border-b border-amber-500/30"
          : "bg-emerald-500/10 text-emerald-300 border-b border-emerald-500/20",
      ].join(" ")}
    >
      <span className="inline-block h-1.5 w-1.5 rounded-full bg-current opacity-80" />
      <span>
        Quant OS Pro Trial: <strong className="font-semibold">Noch {daysRemaining} {dayWord} verbleibend</strong>
        <span className="ml-1 opacity-60">({trialTotalDays - daysRemaining}/{trialTotalDays} Tage genutzt)</span>
      </span>
    </div>
  );
}
