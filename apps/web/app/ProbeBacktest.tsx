"use client";

/**
 * Self-contained demo backtest for the onboarding tour's "AHA-moment" step.
 *
 * Deliberately NOT calling the API: it must produce an instant, always-working visual
 * result even before the sidecar backend is up (offline / first launch). The equity
 * curve is a deterministic, seeded sample inspired by the catalogued Turn-of-Month
 * overlay (strategy 0050) — clearly labelled as a demo, never sold as live numbers.
 *
 * Memory note: a single interval drives the reveal animation and is always cleared on
 * unmount or replay, so repeated tour runs leak nothing.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

interface Point {
  t: number;
  label: string;
  equity: number;
}

/** Tiny deterministic PRNG (mulberry32) so the demo curve is identical every run. */
function mulberry32(seed: number) {
  return function () {
    seed |= 0;
    seed = (seed + 0x6d2b79f5) | 0;
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const START_EQUITY = 10_000;
const MONTHS = 36;

/** Build ~3 years of monthly equity: steady upward drift with small, realistic dips. */
function buildSeries(): Point[] {
  const rnd = mulberry32(50); // seed 50 → a nod to strategy 0050
  const pts: Point[] = [];
  let equity = START_EQUITY;
  const start = new Date(2021, 0, 1);
  for (let i = 0; i <= MONTHS; i++) {
    if (i > 0) {
      // ~+0.9%/month drift, ±2% noise, occasional shallow drawdown.
      const drift = 0.009;
      const noise = (rnd() - 0.5) * 0.04;
      const shock = rnd() < 0.12 ? -(0.02 + rnd() * 0.03) : 0;
      equity *= 1 + drift + noise + shock;
    }
    const d = new Date(start.getFullYear(), start.getMonth() + i, 1);
    pts.push({
      t: i,
      label: d.toLocaleDateString("de-DE", { month: "short", year: "2-digit" }),
      equity: Math.round(equity),
    });
  }
  return pts;
}

/** Honest descriptive stats computed from the demo series itself. */
function stats(series: Point[]) {
  const first = series[0].equity;
  const last = series[series.length - 1].equity;
  const years = MONTHS / 12;
  const cagr = Math.pow(last / first, 1 / years) - 1;
  const rets = series.slice(1).map((p, i) => p.equity / series[i].equity - 1);
  const mean = rets.reduce((a, b) => a + b, 0) / rets.length;
  const sd = Math.sqrt(rets.reduce((a, b) => a + (b - mean) ** 2, 0) / rets.length);
  const sharpe = sd > 0 ? (mean / sd) * Math.sqrt(12) : 0;
  let peak = -Infinity;
  let maxDd = 0;
  for (const p of series) {
    peak = Math.max(peak, p.equity);
    maxDd = Math.min(maxDd, p.equity / peak - 1);
  }
  return { cagr, sharpe, maxDd, last };
}

export default function ProbeBacktest() {
  const series = useMemo(buildSeries, []);
  const summary = useMemo(() => stats(series), [series]);
  const [revealed, setRevealed] = useState(0); // # of points drawn so far
  const [running, setRunning] = useState(false);
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);

  const clear = useCallback(() => {
    if (timer.current) {
      clearInterval(timer.current);
      timer.current = null;
    }
  }, []);

  const run = useCallback(() => {
    clear();
    setRevealed(0);
    setRunning(true);
    timer.current = setInterval(() => {
      setRevealed((n) => {
        if (n >= series.length) {
          clear();
          setRunning(false);
          return n;
        }
        return n + 1;
      });
    }, 45);
  }, [series.length, clear]);

  // Always tidy up the interval on unmount.
  useEffect(() => clear, [clear]);

  const shown = series.slice(0, revealed);
  const done = revealed >= series.length;

  return (
    <div className="w-full">
      <div className="mb-2 flex items-center justify-between">
        <span className="text-[11px] uppercase tracking-widest text-zinc-500">
          Demo · Turn-of-Month-Strategie · 10.000 € Start
        </span>
        <button
          onClick={run}
          className="flex items-center gap-1.5 rounded-md bg-emerald-500 px-3 py-1.5 text-xs font-semibold text-emerald-950 transition hover:bg-emerald-400"
        >
          {!running && (
            <svg className="h-3 w-3" viewBox="0 0 12 12" fill="currentColor" aria-hidden>
              <path d="M3 2.2v7.6a.4.4 0 0 0 .62.34l6-3.8a.4.4 0 0 0 0-.68l-6-3.8A.4.4 0 0 0 3 2.2z" />
            </svg>
          )}
          {running ? "läuft…" : done ? "Erneut auswerten" : "Backtest starten"}
        </button>
      </div>

      <div className="h-44 w-full rounded-lg border border-zinc-800 bg-zinc-950/60 p-2">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={shown} margin={{ top: 6, right: 8, bottom: 0, left: -8 }}>
            <defs>
              <linearGradient id="probeFill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#22c55e" stopOpacity={0.45} />
                <stop offset="100%" stopColor="#22c55e" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
            <XAxis dataKey="label" tick={{ fill: "#71717a", fontSize: 9 }} interval={5} minTickGap={16} />
            <YAxis
              tick={{ fill: "#71717a", fontSize: 9 }}
              width={44}
              domain={["dataMin", "dataMax"]}
              tickFormatter={(v) => `${Math.round(v / 1000)}k`}
            />
            <Tooltip
              contentStyle={{ background: "#18181b", border: "1px solid #3f3f46", fontSize: 12 }}
              formatter={(v) => [`${Number(v).toLocaleString("de-DE")} €`, "Depot"]}
            />
            <Area
              type="monotone"
              dataKey="equity"
              stroke="#22c55e"
              strokeWidth={2}
              fill="url(#probeFill)"
              isAnimationActive={false}
              dot={false}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>

      {/* Headline stats fade in once the run is complete. */}
      <div
        className={`mt-3 grid grid-cols-3 gap-2 transition-opacity duration-500 ${
          done ? "opacity-100" : "opacity-30"
        }`}
      >
        <Stat label="Endkapital" value={done ? `${summary.last.toLocaleString("de-DE")} €` : "—"} good />
        <Stat label="Ø Rendite / Jahr" value={done ? `+${(summary.cagr * 100).toFixed(1)} %` : "—"} good />
        <Stat label="Größter Rücksetzer" value={done ? `${(summary.maxDd * 100).toFixed(1)} %` : "—"} />
      </div>
      <p className="mt-2 text-[10px] leading-snug text-zinc-600">
        Beispiel-Illustration zum Kennenlernen — keine Anlageempfehlung. Echte Backtests mit
        Kosten, Signifikanztests und Out-of-Sample findest du unter „Strategies".
      </p>
    </div>
  );
}

function Stat({ label, value, good }: { label: string; value: string; good?: boolean }) {
  return (
    <div className="rounded-lg border border-zinc-800 bg-zinc-900/60 px-3 py-2 text-center">
      <div className={`text-base font-semibold ${good ? "text-emerald-300" : "text-zinc-200"}`}>
        {value}
      </div>
      <div className="text-[10px] uppercase tracking-wide text-zinc-500">{label}</div>
    </div>
  );
}
