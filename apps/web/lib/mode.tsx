"use client";

import { createContext, useContext, useEffect, useState } from "react";

// Global UI mode (Phase 3.3): Simple hides advanced/research surfaces, Developer shows
// everything. Persisted in localStorage; first render is always "simple" so SSR and the
// initial client render agree (no hydration mismatch), then the saved value is applied.
export type UiMode = "simple" | "developer";

interface ModeContextValue {
  mode: UiMode;
  isDev: boolean;
  setMode: (m: UiMode) => void;
  toggle: () => void;
}

const ModeContext = createContext<ModeContextValue>({
  mode: "simple",
  isDev: false,
  setMode: () => {},
  toggle: () => {},
});

const STORAGE_KEY = "qos_mode";

export function ModeProvider({ children }: { children: React.ReactNode }) {
  const [mode, setModeState] = useState<UiMode>("simple");

  useEffect(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      if (saved === "simple" || saved === "developer") setModeState(saved);
    } catch {
      /* localStorage unavailable */
    }
  }, []);

  const setMode = (m: UiMode) => {
    setModeState(m);
    try {
      localStorage.setItem(STORAGE_KEY, m);
    } catch {
      /* ignore */
    }
  };

  const value: ModeContextValue = {
    mode,
    isDev: mode === "developer",
    setMode,
    toggle: () => setMode(mode === "developer" ? "simple" : "developer"),
  };
  return <ModeContext.Provider value={value}>{children}</ModeContext.Provider>;
}

export const useMode = () => useContext(ModeContext);
