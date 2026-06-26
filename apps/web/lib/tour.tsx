"use client";

/**
 * Onboarding tour state — "The 60-Second AHA-Moment".
 *
 * A dependency-free guided walkthrough (no react-joyride: it has peer-dependency
 * friction with React 19 / Next 15 and ships its own portals + ~40 KB, which works
 * against the desktop memory budget). This context owns the run state; the visual
 * overlay lives in {@link app/OnboardingTour.tsx}.
 *
 * First-run behaviour: the tour auto-starts once, gated by a localStorage flag
 * (`qos_onboarded`). It can always be restarted from the "?" button in the NavBar.
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";

const STORAGE_KEY = "qos_onboarded";

export type TourPlacement = "top" | "bottom" | "left" | "right" | "center";
export type TourKind = "spotlight" | "probe";

/** Named icon from lib/icons.tsx (kept as a string so the data stays serialisable). */
export type TourIcon = "compass" | "radar" | "target" | "chart" | "check";

export interface TourStep {
  id: string;
  /** Navigate here before showing the step (skipped if already there). */
  route?: string;
  /** `data-tour` value of the element to spotlight; absent → centered card. */
  target?: string;
  icon?: TourIcon;
  title: string;
  /** Beginner-friendly copy — plain language, professional tone, no formulas. */
  body: React.ReactNode;
  placement?: TourPlacement;
  kind?: TourKind;
}

// The curated beginner path. Order matters: a soft welcome, the two "instant
// understanding" surfaces, a hands-on probe backtest, then a launch pad.
export const TOUR_STEPS: TourStep[] = [
  {
    id: "welcome",
    icon: "compass",
    title: "Willkommen bei Quant OS",
    body: (
      <>
        Quant OS verdichtet Marktdaten, institutionelle Positionierung und statistisch
        geprüfte Strategien zu klaren Entscheidungen. Diese kurze Einführung stellt dir die
        drei zentralen Werkzeuge vor — in weniger als einer Minute. Du kannst sie jederzeit
        über das Fragezeichen oben rechts erneut aufrufen.
      </>
    ),
    placement: "center",
  },
  {
    id: "radar",
    route: "/radar",
    target: "radar",
    icon: "radar",
    title: "Market Weather Radar",
    body: (
      <>
        Das Radar ordnet jeden Markt automatisch nach zwei Dimensionen ein:{" "}
        <strong>Schwankungsbreite</strong> (ruhig oder turbulent) und{" "}
        <strong>Richtung</strong> (Trend oder Seitwärtsphase). Daraus ergeben sich vier
        Regime. So erkennst du sofort, ob das Umfeld eine Strategie begünstigt — ohne selbst
        Kennzahlen berechnen zu müssen. <span className="text-emerald-300">Grün</span>{" "}
        signalisiert ein konstruktives, <span className="text-red-300">Rot</span> ein
        erhöht riskantes Umfeld.
      </>
    ),
    placement: "bottom",
  },
  {
    id: "cot",
    route: "/cot",
    target: "cot",
    icon: "target",
    title: "Institutionelle Positionierung",
    body: (
      <>
        Große Marktteilnehmer — Banken und Fonds — müssen ihre Futures-Positionen
        wöchentlich offenlegen (Commitments of Traders). Quant OS wertet diese Berichte aus
        und zeigt dir, wo das professionelle Kapital steht. <strong>Extreme, einseitige
        Positionierungen</strong> markieren historisch häufig Wendepunkte, bevor sie sich im
        Kurs zeigen.
      </>
    ),
    placement: "bottom",
  },
  {
    id: "probe",
    route: "/",
    icon: "chart",
    title: "Strategien historisch prüfen",
    body: (
      <>
        Ein Backtest spielt eine Handelsregel auf echten historischen Kursen durch und
        zeigt, wie sich ein Startkapital entwickelt hätte. Starte hier eine
        Beispielauswertung — die Equity-Kurve erscheint sofort. In Quant OS durchläuft jede
        Strategie zusätzlich <strong>Kosten-, Signifikanz- und Out-of-Sample-Tests</strong>,
        bevor sie als belastbar gilt.
      </>
    ),
    placement: "center",
    kind: "probe",
  },
  {
    id: "done",
    icon: "check",
    title: "Bereit zum Start",
    body: (
      <>
        Du kennst nun die drei Kernbausteine: <strong>Regime-Analyse</strong>,{" "}
        <strong>institutionelle Positionierung</strong> und <strong>geprüfte Backtests</strong>.
        Vertiefe dein Wissen strukturiert in der Academy — oder beginne direkt mit der
        Marktanalyse.
      </>
    ),
    placement: "center",
  },
];

interface TourContextValue {
  active: boolean;
  stepIndex: number;
  steps: TourStep[];
  step: TourStep | null;
  /** True once the first-run flag has been read (avoids an SSR flash). */
  ready: boolean;
  hasOnboarded: boolean;
  start: () => void;
  stop: (markDone?: boolean) => void;
  next: () => void;
  prev: () => void;
  goto: (i: number) => void;
}

const TourContext = createContext<TourContextValue>({
  active: false,
  stepIndex: 0,
  steps: TOUR_STEPS,
  step: null,
  ready: false,
  hasOnboarded: false,
  start: () => {},
  stop: () => {},
  next: () => {},
  prev: () => {},
  goto: () => {},
});

export function TourProvider({ children }: { children: React.ReactNode }) {
  const [active, setActive] = useState(false);
  const [stepIndex, setStepIndex] = useState(0);
  const [hasOnboarded, setHasOnboarded] = useState(false);
  const [ready, setReady] = useState(false);

  // Read the first-run flag once on mount; auto-start for brand-new users.
  useEffect(() => {
    let onboarded = false;
    try {
      onboarded = localStorage.getItem(STORAGE_KEY) === "1";
    } catch {
      /* localStorage unavailable */
    }
    setHasOnboarded(onboarded);
    setReady(true);
    if (!onboarded) {
      // Small delay so the first route has painted before we navigate the tour.
      const t = setTimeout(() => {
        setStepIndex(0);
        setActive(true);
      }, 600);
      return () => clearTimeout(t);
    }
  }, []);

  const markOnboarded = useCallback(() => {
    setHasOnboarded(true);
    try {
      localStorage.setItem(STORAGE_KEY, "1");
    } catch {
      /* ignore */
    }
  }, []);

  const start = useCallback(() => {
    setStepIndex(0);
    setActive(true);
  }, []);

  const stop = useCallback(
    (markDone = true) => {
      setActive(false);
      if (markDone) markOnboarded();
    },
    [markOnboarded],
  );

  const next = useCallback(() => {
    setStepIndex((i) => {
      if (i >= TOUR_STEPS.length - 1) {
        setActive(false);
        markOnboarded();
        return i;
      }
      return i + 1;
    });
  }, [markOnboarded]);

  const prev = useCallback(() => setStepIndex((i) => Math.max(0, i - 1)), []);
  const goto = useCallback(
    (i: number) => setStepIndex(Math.max(0, Math.min(TOUR_STEPS.length - 1, i))),
    [],
  );

  const value = useMemo<TourContextValue>(
    () => ({
      active,
      stepIndex,
      steps: TOUR_STEPS,
      step: active ? TOUR_STEPS[stepIndex] ?? null : null,
      ready,
      hasOnboarded,
      start,
      stop,
      next,
      prev,
      goto,
    }),
    [active, stepIndex, ready, hasOnboarded, start, stop, next, prev, goto],
  );

  return <TourContext.Provider value={value}>{children}</TourContext.Provider>;
}

export const useTour = () => useContext(TourContext);
