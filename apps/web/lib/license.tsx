"use client";

/**
 * License / trial state for the Quant OS Pro desktop build.
 *
 * The React layer is a thin client over the Rust commands in `src-tauri/src/license.rs`
 * (`get_status`, `activate_license`, `recheck_license`). It exposes a single
 * {@link useLicense} hook that the {@link LicenseGuard} consumes to decide between
 * showing the app, the trial banner, or the full-screen subscription wall.
 *
 * Outside of Tauri (plain `npm run dev` website, or a hosted deployment) the gate is
 * intentionally bypassed (`WEB_BYPASS`) so the existing web app keeps working unchanged.
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
} from "react";

// ── configuration the operator must edit before shipping ─────────────────────
/** TODO: replace with your real Lemon Squeezy checkout/sales URL. */
export const BUY_URL = "https://YOUR_STORE.lemonsqueezy.com/buy/YOUR-PRODUCT-ID";
/** When NOT running inside Tauri, treat the app as fully unlocked (web/dev use). */
const WEB_BYPASS = true;

export type LicenseStatus = "LOADING" | "TRIAL" | "EXPIRED" | "LICENSED";

interface StatusReport {
  status: Exclude<LicenseStatus, "LOADING">;
  days_remaining: number;
  trial_total_days: number;
  license_key: string | null;
}

interface LicenseContextValue {
  status: LicenseStatus;
  daysRemaining: number;
  trialTotalDays: number;
  licenseKey: string | null;
  isTauri: boolean;
  /** Validate + persist a key. Resolves `{ ok }`; on failure carries an `error`. */
  activate: (key: string) => Promise<{ ok: boolean; error?: string }>;
  /** Re-read the status from the backend (e.g. after activation). */
  refresh: () => Promise<void>;
}

const LicenseContext = createContext<LicenseContextValue>({
  status: "LOADING",
  daysRemaining: 0,
  trialTotalDays: 7,
  licenseKey: null,
  isTauri: false,
  activate: async () => ({ ok: false, error: "not ready" }),
  refresh: async () => {},
});

/** Detect the Tauri v2 runtime (its IPC globals are injected into the webview). */
function inTauri(): boolean {
  if (typeof window === "undefined") return false;
  return "__TAURI_INTERNALS__" in window || "isTauri" in window;
}

async function invokeCmd<T>(cmd: string, args?: Record<string, unknown>): Promise<T> {
  const { invoke } = await import("@tauri-apps/api/core");
  return invoke<T>(cmd, args);
}

export function LicenseProvider({ children }: { children: React.ReactNode }) {
  const [report, setReport] = useState<StatusReport | null>(null);
  const [status, setStatus] = useState<LicenseStatus>("LOADING");
  const isTauri = inTauri();

  const apply = useCallback((r: StatusReport) => {
    setReport(r);
    setStatus(r.status);
  }, []);

  const refresh = useCallback(async () => {
    if (!isTauri) {
      apply({ status: "LICENSED", days_remaining: -1, trial_total_days: 7, license_key: null });
      return;
    }
    let r = await invokeCmd<StatusReport>("get_status");
    // If a license is on file, re-validate online before revealing the app, so a
    // cancelled subscription locks immediately (network errors keep the grace state).
    if (r.status === "LICENSED") {
      r = await invokeCmd<StatusReport>("recheck_license");
    }
    apply(r);
  }, [isTauri, apply]);

  useEffect(() => {
    if (!isTauri) {
      if (WEB_BYPASS) {
        apply({ status: "LICENSED", days_remaining: -1, trial_total_days: 7, license_key: null });
      } else {
        apply({ status: "EXPIRED", days_remaining: 0, trial_total_days: 7, license_key: null });
      }
      return;
    }
    refresh().catch(() => {
      // A hard IPC failure inside Tauri shouldn't silently unlock — fail closed.
      apply({ status: "EXPIRED", days_remaining: 0, trial_total_days: 7, license_key: null });
    });
  }, [isTauri, refresh, apply]);

  const activate = useCallback(
    async (key: string): Promise<{ ok: boolean; error?: string }> => {
      if (!isTauri) return { ok: false, error: "Lizenzaktivierung nur in der Desktop-App." };
      try {
        const r = await invokeCmd<StatusReport>("activate_license", { key });
        apply(r);
        return { ok: true };
      } catch (e) {
        return { ok: false, error: typeof e === "string" ? e : String(e) };
      }
    },
    [isTauri, apply],
  );

  const value: LicenseContextValue = {
    status,
    daysRemaining: report?.days_remaining ?? 0,
    trialTotalDays: report?.trial_total_days ?? 7,
    licenseKey: report?.license_key ?? null,
    isTauri,
    activate,
    refresh,
  };

  return <LicenseContext.Provider value={value}>{children}</LicenseContext.Provider>;
}

export const useLicense = () => useContext(LicenseContext);

/** Open the external checkout in the system browser (Tauri opener) or a new tab. */
export async function openCheckout(): Promise<void> {
  if (inTauri()) {
    const { openUrl } = await import("@tauri-apps/plugin-opener");
    await openUrl(BUY_URL);
  } else if (typeof window !== "undefined") {
    window.open(BUY_URL, "_blank", "noopener,noreferrer");
  }
}
