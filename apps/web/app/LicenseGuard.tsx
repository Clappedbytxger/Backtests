"use client";

import { useLicense } from "@/lib/license";
import SubscriptionScreen from "./SubscriptionScreen";
import TrialBanner from "./TrialBanner";

/**
 * Global protection layer. Decides, from the gate status, what the user sees:
 *
 * * `LOADING`  → a minimal splash while the Rust backend is queried.
 * * `EXPIRED`  → ONLY the full-screen {@link SubscriptionScreen} (dashboard unmounted).
 * * `TRIAL`    → the app, with a {@link TrialBanner} strip on top.
 * * `LICENSED` → the app, no banner.
 */
export default function LicenseGuard({ children }: { children: React.ReactNode }) {
  const { status } = useLicense();

  if (status === "LOADING") {
    return (
      <div className="flex min-h-screen items-center justify-center bg-zinc-950">
        <div className="flex items-center gap-2 text-sm text-zinc-500">
          <span className="inline-block h-2 w-2 animate-pulse rounded-sm bg-emerald-400" />
          Quant OS Pro wird geladen…
        </div>
      </div>
    );
  }

  if (status === "EXPIRED") {
    return <SubscriptionScreen />;
  }

  return (
    <>
      <TrialBanner />
      {children}
    </>
  );
}
