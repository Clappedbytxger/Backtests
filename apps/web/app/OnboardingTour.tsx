"use client";

/**
 * Visual layer for the onboarding tour (state lives in lib/tour.tsx).
 *
 * Renders a full-viewport dim with a rounded "spotlight" cutout around the current
 * step's target element, plus a positioned explainer card. Route-aware: it navigates
 * to the step's page and polls for the `data-tour` anchor; if the anchor never appears
 * (e.g. the page is still loading or the API is down) it falls back to a centred card so
 * the tour can never get stuck. The probe step renders an embedded demo backtest.
 *
 * Memory: every listener/rAF/timeout is cleaned up; nothing runs while the tour is idle.
 */

import { useEffect, useRef, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { useTour, type TourIcon } from "@/lib/tour";
import {
  IconChart,
  IconCheckCircle,
  IconCompass,
  IconRadar,
  IconTarget,
} from "@/lib/icons";
import ProbeBacktest from "./ProbeBacktest";

const STEP_ICON: Record<TourIcon, (p: { className?: string }) => React.ReactNode> = {
  compass: IconCompass,
  radar: IconRadar,
  target: IconTarget,
  chart: IconChart,
  check: IconCheckCircle,
};

const PAD = 8; // spotlight padding around the target (px)
const MARGIN = 16; // keep the card this far from the viewport edge

// The Tauri static export uses trailingSlash routing ("/radar/"), dev does not ("/radar").
// Normalise so route comparisons work in both builds.
const norm = (p: string) => (p !== "/" && p.endsWith("/") ? p.slice(0, -1) : p);

export default function OnboardingTour() {
  const { active, step, stepIndex, steps, next, prev, stop } = useTour();
  const pathname = usePathname();
  const router = useRouter();

  const [rect, setRect] = useState<DOMRect | null>(null);
  const elRef = useRef<HTMLElement | null>(null);
  const [found, setFound] = useState(0); // bumps when a target element is located

  // 1) Navigate to the step's route if we're not already there.
  useEffect(() => {
    if (!active || !step?.route) return;
    if (norm(pathname) !== norm(step.route)) router.push(step.route);
  }, [active, step, pathname, router]);

  // 2) Locate the target element (poll until it mounts after a route change).
  useEffect(() => {
    elRef.current = null;
    setRect(null);
    if (!active || !step?.target) return;
    if (step.route && norm(pathname) !== norm(step.route)) return; // wait for route to settle

    let raf = 0;
    let tries = 0;
    let cancelled = false;
    const sel = `[data-tour="${step.target}"]`;

    const find = () => {
      if (cancelled) return;
      const el = document.querySelector(sel) as HTMLElement | null;
      if (el) {
        elRef.current = el;
        el.scrollIntoView({ block: "center", behavior: "smooth" });
        setRect(el.getBoundingClientRect());
        setFound((n) => n + 1);
      } else if (tries++ < 150) {
        raf = requestAnimationFrame(find);
      } // else: give up → centred fallback (rect stays null)
    };
    find();
    return () => {
      cancelled = true;
      cancelAnimationFrame(raf);
    };
  }, [active, step, pathname]);

  // 3) Keep the spotlight aligned while the target element is on screen.
  useEffect(() => {
    if (!active || !elRef.current) return;
    const update = () => {
      if (elRef.current) setRect(elRef.current.getBoundingClientRect());
    };
    update();
    window.addEventListener("scroll", update, true); // capture → catches nested scrollers
    window.addEventListener("resize", update);
    return () => {
      window.removeEventListener("scroll", update, true);
      window.removeEventListener("resize", update);
    };
  }, [active, found]);

  // 4) Esc skips the tour.
  useEffect(() => {
    if (!active) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") stop(true);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [active, stop]);

  if (!active || !step) return null;

  const isLast = stepIndex >= steps.length - 1;
  const isProbe = step.kind === "probe";
  const useSpotlight = !!rect && !isProbe && step.placement !== "center";
  const cardWidth = isProbe ? 480 : 360;
  const cardPos = computeCardPosition(rect, step.placement, useSpotlight, cardWidth);

  return (
    <div className="fixed inset-0 z-[100]" role="dialog" aria-modal="true" aria-label="Onboarding-Tour">
      {/* Dim layer. With a target → SVG mask cutout; otherwise a flat dim. */}
      {useSpotlight && rect ? (
        <svg className="absolute inset-0 h-full w-full" aria-hidden>
          <defs>
            <mask id="qos-tour-hole">
              <rect x="0" y="0" width="100%" height="100%" fill="white" />
              <rect
                x={rect.left - PAD}
                y={rect.top - PAD}
                width={rect.width + PAD * 2}
                height={rect.height + PAD * 2}
                rx={14}
                fill="black"
              />
            </mask>
          </defs>
          <rect x="0" y="0" width="100%" height="100%" fill="rgba(0,0,0,0.74)" mask="url(#qos-tour-hole)" />
        </svg>
      ) : (
        <div className="absolute inset-0 bg-black/75 backdrop-blur-[2px]" />
      )}

      {/* Glow ring around the spotlighted element. */}
      {useSpotlight && rect && (
        <div
          className="pointer-events-none absolute rounded-2xl ring-2 ring-emerald-400/80 transition-all duration-300"
          style={{
            left: rect.left - PAD,
            top: rect.top - PAD,
            width: rect.width + PAD * 2,
            height: rect.height + PAD * 2,
            boxShadow: "0 0 0 9999px rgba(0,0,0,0)", // ensures stacking; mask already dims
          }}
        />
      )}

      {/* Explainer / probe card. */}
      <div
        className="absolute w-[calc(100vw-2rem)] rounded-2xl border border-zinc-700 bg-zinc-900/95 p-5 shadow-2xl shadow-black/60 backdrop-blur"
        style={{ left: cardPos.left, top: cardPos.top, maxWidth: cardWidth }}
      >
        <button
          onClick={() => stop(true)}
          aria-label="Tour überspringen"
          className="absolute right-3 top-3 text-zinc-500 transition hover:text-zinc-200"
        >
          <svg className="h-4 w-4" viewBox="0 0 20 20" fill="none">
            <path d="M5 5l10 10M15 5L5 15" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
          </svg>
        </button>

        <div className="flex items-start gap-3 pr-6">
          {step.icon &&
            (() => {
              const Icon = STEP_ICON[step.icon];
              return (
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-emerald-500/25 bg-emerald-500/10 text-emerald-300">
                  <Icon className="h-5 w-5" />
                </div>
              );
            })()}
          <div>
            <div className="text-[11px] font-medium uppercase tracking-[0.18em] text-zinc-500">
              Schritt {stepIndex + 1} von {steps.length}
            </div>
            <h2 className="mt-0.5 text-lg font-semibold tracking-tight text-zinc-100">
              {step.title}
            </h2>
          </div>
        </div>
        <p className="mt-3 text-sm leading-relaxed text-zinc-300">{step.body}</p>

        {isProbe && (
          <div className="mt-4">
            <ProbeBacktest />
          </div>
        )}

        {/* progress + controls */}
        <div className="mt-5 flex items-center justify-between">
          <div className="flex items-center gap-1.5">
            {steps.map((s, i) => (
              <span
                key={s.id}
                className={`h-1.5 rounded-full transition-all ${
                  i === stepIndex ? "w-5 bg-emerald-400" : "w-1.5 bg-zinc-700"
                }`}
              />
            ))}
          </div>
          <div className="flex items-center gap-2">
            {stepIndex > 0 && (
              <button
                onClick={prev}
                className="rounded-md px-3 py-1.5 text-sm text-zinc-400 transition hover:text-zinc-100"
              >
                Zurück
              </button>
            )}
            <button
              onClick={() => (isLast ? stop(true) : next())}
              className="rounded-md bg-emerald-500 px-4 py-1.5 text-sm font-semibold text-emerald-950 transition hover:bg-emerald-400"
            >
              {isLast ? "Loslegen" : "Weiter"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

/** Position the card relative to the target rect (or centre it when there is none). */
function computeCardPosition(
  rect: DOMRect | null,
  placement: string | undefined,
  useSpotlight: boolean,
  cardWidth: number,
): { left: number; top: number } {
  if (typeof window === "undefined") return { left: 0, top: 0 };
  const vw = window.innerWidth;
  const vh = window.innerHeight;
  const clampLeft = (l: number) => Math.max(MARGIN, Math.min(l, vw - cardWidth - MARGIN));
  const estH = 280; // rough card height for vertical clamping
  const clampTop = (t: number) => Math.max(MARGIN, Math.min(t, vh - estH - MARGIN));

  if (!useSpotlight || !rect || placement === "center") {
    return { left: clampLeft((vw - cardWidth) / 2), top: clampTop((vh - estH) / 2) };
  }
  switch (placement) {
    case "top":
      return { left: clampLeft(rect.left), top: clampTop(rect.top - estH - 16) };
    case "left":
      return { left: clampLeft(rect.left - cardWidth - 16), top: clampTop(rect.top) };
    case "right":
      return { left: clampLeft(rect.right + 16), top: clampTop(rect.top) };
    case "bottom":
    default:
      return { left: clampLeft(rect.left), top: clampTop(rect.bottom + 16) };
  }
}
