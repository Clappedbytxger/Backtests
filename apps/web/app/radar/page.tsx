"use client";

import { useCallback, useEffect, useState } from "react";
import {
  getRegimeCurrent,
  getRegimeOverview,
  getRegimePerformance,
  getRegimeTimeline,
  getRegimeUniverse,
  type RegimeCode,
  type RegimeCurrentResponse,
  type RegimeOverviewResponse,
  type RegimePerformanceResponse,
  type RegimeTimelineResponse,
  type RegimeUniverseItem,
} from "@/lib/api";
import RegimeTimeline from "./RegimeTimeline";
import PerformanceMatrix from "./PerformanceMatrix";

const QUADRANTS: { row: string; cells: { code: RegimeCode; col: string }[] }[] = [
  { row: "High Vol", cells: [
    { code: "high_vol_trend", col: "Trending" },
    { code: "high_vol_range", col: "Sideways" },
  ] },
  { row: "Low Vol", cells: [
    { code: "low_vol_trend", col: "Trending" },
    { code: "low_vol_range", col: "Sideways" },
  ] },
];

const STRATEGIES = [
  { id: "buy_hold", label: "Buy & Hold" },
  { id: "long_trend", label: "Long nur im Trend" },
  { id: "long_quiet", label: "Long nur in Ruhe" },
];

const cls = (...x: (string | false | undefined)[]) => x.filter(Boolean).join(" ");

export default function RadarPage() {
  const [universe, setUniverse] = useState<RegimeUniverseItem[]>([]);
  const [ticker, setTicker] = useState("SPY");
  const [strategy, setStrategy] = useState("buy_hold");
  const [current, setCurrent] = useState<RegimeCurrentResponse | null>(null);
  const [timeline, setTimeline] = useState<RegimeTimelineResponse | null>(null);
  const [perf, setPerf] = useState<RegimePerformanceResponse | null>(null);
  const [overview, setOverview] = useState<RegimeOverviewResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    getRegimeUniverse().then((r) => setUniverse(r.universe)).catch((e) => setError(String(e)));
    getRegimeOverview().then(setOverview).catch(() => {});
  }, []);

  const load = useCallback((t: string, strat: string) => {
    setLoading(true);
    Promise.all([
      getRegimeCurrent(t).then(setCurrent),
      getRegimeTimeline(t, 3).then(setTimeline),
      getRegimePerformance(t, strat).then(setPerf),
    ])
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => { load(ticker, strategy); }, [ticker, strategy, load]);

  if (error)
    return (
      <main className="mx-auto max-w-7xl p-8">
        <div className="rounded-lg border border-red-900 bg-red-950/40 p-4 text-sm text-red-300">
          API nicht erreichbar ({error}). Starte sie mit{" "}
          <code>uvicorn apps.api.main:app --port 8000</code>.
        </div>
      </main>
    );

  const snap = current?.snapshot;
  const active = snap?.regime ?? null;
  const m = snap?.metrics;

  return (
    <main className="mx-auto max-w-7xl p-6">
      {/* ── header ─────────────────────────────────────────────── */}
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="flex items-center gap-2 text-3xl font-semibold tracking-tight">
            <span className="text-amber-300">◴</span> Market Weather Radar
          </h1>
          <p className="mt-1 text-sm text-zinc-400">
            Mathematische Klassifizierung der Marktlage — Volatilität × Trend → vier Regimes.
          </p>
        </div>
        <select
          value={ticker}
          onChange={(e) => setTicker(e.target.value)}
          className="rounded-md border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm text-zinc-100"
        >
          {universe.map((u) => (
            <option key={u.ticker} value={u.ticker}>
              {u.name} ({u.ticker})
            </option>
          ))}
        </select>
      </div>

      {/* ── top row: radar widget + universe grid ──────────────── */}
      <div className="mt-6 grid grid-cols-1 gap-5 lg:grid-cols-3">
        {/* the big radar card */}
        <section
          className="relative overflow-hidden rounded-2xl border p-5 lg:col-span-2"
          style={{
            borderColor: (snap?.color ?? "#3f3f46") + "66",
            background: `radial-gradient(120% 120% at 0% 0%, ${(snap?.color ?? "#18181b")}22, #09090b 60%)`,
          }}
        >
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <div className="text-xs uppercase tracking-widest text-zinc-500">
                {current?.meta.name} · {ticker} · Stand {snap?.asof ?? "—"}
              </div>
              <div className="mt-2 flex items-center gap-3">
                <span
                  className="inline-block h-5 w-5 rounded-full"
                  style={{ background: snap?.color, boxShadow: `0 0 18px ${snap?.color}` }}
                />
                <span className="text-3xl font-bold tracking-tight" style={{ color: snap?.color }}>
                  {snap?.label ?? "—"}
                </span>
                {snap?.direction && (
                  <span
                    className={cls(
                      "rounded-full border px-2.5 py-0.5 text-xs",
                      snap.direction === "bull" && "border-emerald-600 text-emerald-300",
                      snap.direction === "bear" && "border-red-600 text-red-300",
                      snap.direction === "neutral" && "border-zinc-600 text-zinc-400",
                    )}
                  >
                    {snap.direction_label}
                  </span>
                )}
              </div>
              <p className="mt-2 max-w-md text-sm text-zinc-400">{snap?.description}</p>
            </div>

            {/* 2×2 weather quadrant */}
            <div className="grid grid-cols-[auto_repeat(2,1fr)] gap-1.5 text-center">
              <div />
              <div className="text-[10px] uppercase tracking-wide text-zinc-500">Trend</div>
              <div className="text-[10px] uppercase tracking-wide text-zinc-500">Seitw.</div>
              {QUADRANTS.map((q) => (
                <FragmentRow key={q.row} label={q.row}>
                  {q.cells.map((cell) => {
                    const on = cell.code === active;
                    const color = current?.distribution[cell.code]?.color ?? "#3f3f46";
                    return (
                      <div
                        key={cell.code}
                        className={cls(
                          "flex h-12 w-16 items-center justify-center rounded-md border text-[10px] transition",
                          on ? "font-semibold text-zinc-950" : "text-zinc-500",
                        )}
                        style={{
                          background: on ? color : color + "1a",
                          borderColor: on ? color : "#27272a",
                          boxShadow: on ? `0 0 16px ${color}aa` : "none",
                        }}
                      >
                        {cell.col}
                      </div>
                    );
                  })}
                </FragmentRow>
              ))}
            </div>
          </div>

          {/* gauges + distribution */}
          <div className="mt-5 grid grid-cols-2 gap-4 sm:grid-cols-4">
            <Gauge label="ADX (Trendstärke)" value={m?.adx ?? null} max={50} hint=">22 = Trend" />
            <Gauge label="Vol-Rank" value={m?.vol_rank != null ? m.vol_rank * 100 : null} max={100} suffix="%" hint=">55 = High Vol" />
            <Gauge label="ATR % vom Preis" value={m?.atr_pct != null ? m.atr_pct * 100 : null} max={6} suffix="%" digits={2} />
            <Gauge label="Realisierte Vol" value={m?.hist_vol != null ? m.hist_vol * 100 : null} max={80} suffix="%" />
          </div>

          {/* time-in-regime distribution bar */}
          {current && (
            <div className="mt-5">
              <div className="mb-1.5 text-[10px] uppercase tracking-wide text-zinc-500">
                Zeitanteil je Regime (8J)
              </div>
              <div className="flex h-3 overflow-hidden rounded-full">
                {(Object.keys(current.distribution) as RegimeCode[]).map((c) => {
                  const d = current.distribution[c];
                  return (
                    <div
                      key={c}
                      title={`${d.label}: ${(d.pct * 100).toFixed(1)}%`}
                      style={{ width: `${d.pct * 100}%`, background: d.color }}
                    />
                  );
                })}
              </div>
            </div>
          )}
          {loading && (
            <div className="absolute right-4 top-4 text-[10px] text-zinc-500">aktualisiere…</div>
          )}
        </section>

        {/* universe overview grid */}
        <section className="rounded-2xl border border-zinc-800 bg-zinc-900/30 p-4">
          <div className="mb-3 text-xs uppercase tracking-widest text-zinc-500">
            Marktbreite — alle Assets jetzt
          </div>
          <div className="grid grid-cols-2 gap-2">
            {overview?.items.map((it) => {
              const c = it.snapshot?.color ?? "#3f3f46";
              return (
                <button
                  key={it.ticker}
                  onClick={() => setTicker(it.ticker)}
                  className={cls(
                    "flex flex-col items-start gap-1 rounded-lg border p-2.5 text-left transition hover:border-zinc-600",
                    it.ticker === ticker ? "border-zinc-500" : "border-zinc-800",
                  )}
                  style={{ background: c + "14" }}
                >
                  <div className="flex w-full items-center justify-between">
                    <span className="text-xs font-medium text-zinc-200">{it.ticker}</span>
                    <span className="h-2.5 w-2.5 rounded-full" style={{ background: c, boxShadow: `0 0 8px ${c}` }} />
                  </div>
                  <span className="text-[10px] leading-tight text-zinc-500">
                    {it.snapshot?.label ?? it.error ?? "—"}
                  </span>
                </button>
              );
            })}
          </div>
        </section>
      </div>

      {/* ── regime-shaded timeline ─────────────────────────────── */}
      <section className="mt-6 rounded-2xl border border-zinc-800 bg-zinc-900/30 p-5">
        <div className="mb-1 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-zinc-200">
            Regime-Timeline · {current?.meta.name} (3 Jahre)
          </h2>
          <span className="text-[11px] text-zinc-500">Hintergrund = Marktregime · Linie = Kurs + MAs</span>
        </div>
        {timeline ? <RegimeTimeline data={timeline} /> : <Skeleton h={340} />}
      </section>

      {/* ── performance matrix ─────────────────────────────────── */}
      <section className="mt-6 rounded-2xl border border-zinc-800 bg-zinc-900/30 p-5">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="text-sm font-semibold text-zinc-200">
              Regime-Performance-Matrix — Soll vs. Ist
            </h2>
            <p className="text-[11px] text-zinc-500">
              In welchem Regime verdient diese Regel? Beweist den Agenten-Tipp (allowed_market_regimes).
            </p>
          </div>
          <div className="flex gap-1.5">
            {STRATEGIES.map((s) => (
              <button
                key={s.id}
                onClick={() => setStrategy(s.id)}
                className={cls(
                  "rounded-md border px-3 py-1.5 text-xs transition",
                  strategy === s.id
                    ? "border-amber-500/60 bg-amber-500/10 text-amber-200"
                    : "border-zinc-700 text-zinc-400 hover:border-zinc-500",
                )}
              >
                {s.label}
              </button>
            ))}
          </div>
        </div>
        {perf?.overall && (
          <div className="mb-4 flex gap-6 text-xs text-zinc-400">
            <span>
              Gesamt-Return:{" "}
              <span className="font-mono text-zinc-200">
                {(perf.overall.total_return * 100).toFixed(1)}%
              </span>
            </span>
            <span>
              Gesamt-Sharpe:{" "}
              <span className="font-mono text-zinc-200">{perf.overall.sharpe.toFixed(2)}</span>
            </span>
          </div>
        )}
        {perf ? <PerformanceMatrix data={perf} /> : <Skeleton h={260} />}
      </section>
    </main>
  );
}

function FragmentRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <>
      <div className="flex items-center pr-1 text-[10px] uppercase tracking-wide text-zinc-500">
        {label}
      </div>
      {children}
    </>
  );
}

function Gauge({
  label,
  value,
  max,
  suffix = "",
  hint,
  digits = 0,
}: {
  label: string;
  value: number | null;
  max: number;
  suffix?: string;
  hint?: string;
  digits?: number;
}) {
  const pct = value == null ? 0 : Math.max(0, Math.min(value / max, 1)) * 100;
  return (
    <div className="rounded-lg border border-zinc-800 bg-zinc-950/40 p-3">
      <div className="text-[10px] uppercase tracking-wide text-zinc-500">{label}</div>
      <div className="mt-1 font-mono text-lg text-zinc-100">
        {value == null ? "—" : value.toFixed(digits)}
        <span className="text-xs text-zinc-500">{suffix}</span>
      </div>
      <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-zinc-800">
        <div className="h-full rounded-full bg-zinc-400" style={{ width: `${pct}%` }} />
      </div>
      {hint && <div className="mt-1 text-[9px] text-zinc-600">{hint}</div>}
    </div>
  );
}

function Skeleton({ h }: { h: number }) {
  return <div className="animate-pulse rounded-lg bg-zinc-900/60" style={{ height: h }} />;
}
