"use client";

import { useCallback, useEffect, useState } from "react";
import {
  getPairDetail,
  getPairHeatmap,
  getPairScan,
  getPairUniverse,
  type PairDetailResponse,
  type PairGroup,
  type PairHeatmapResponse,
  type PairScanResponse,
  type PairSignal,
  type PairStat,
} from "@/lib/api";
import SpreadChart from "./SpreadChart";
import CointHeatmap from "./CointHeatmap";
import BacktestPanel from "./BacktestPanel";

const cls = (...x: (string | false | undefined)[]) => x.filter(Boolean).join(" ");

const SIGNAL_BADGE: Record<PairSignal, { label: string; klass: string }> = {
  long_spread: { label: "LONG", klass: "border-emerald-600 bg-emerald-500/10 text-emerald-300" },
  short_spread: { label: "SHORT", klass: "border-red-600 bg-red-500/10 text-red-300" },
  neutral: { label: "neutral", klass: "border-zinc-700 text-zinc-500" },
};

const fmtP = (p: number | null) => (p == null ? "—" : p < 0.001 ? "<0.001" : p.toFixed(3));
const fmtHL = (h: number | null) => (h == null ? "∞" : `${h.toFixed(0)}d`);
const fmtZ = (z: number | null) => (z == null ? "—" : (z >= 0 ? "+" : "") + z.toFixed(2));

export default function PairsPage() {
  const [groups, setGroups] = useState<PairGroup[]>([]);
  const [group, setGroup] = useState("famous");
  const [corr, setCorr] = useState(0.7);
  const [years, setYears] = useState(6);
  const [scan, setScan] = useState<PairScanResponse | null>(null);
  const [heatmap, setHeatmap] = useState<PairHeatmapResponse | null>(null);
  const [detail, setDetail] = useState<PairDetailResponse | null>(null);
  const [sel, setSel] = useState<{ a: string; b: string } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [scanning, setScanning] = useState(false);

  useEffect(() => {
    getPairUniverse().then((r) => setGroups(r.groups)).catch((e) => setError(String(e)));
  }, []);

  const loadDetail = useCallback((a: string, b: string, yrs: number) => {
    setSel({ a, b });
    getPairDetail(a, b, yrs).then(setDetail).catch((e) => setError(String(e)));
  }, []);

  const runScan = useCallback(
    (g: string, c: number, yrs: number) => {
      setScanning(true);
      setDetail(null);
      setSel(null);
      Promise.all([
        getPairScan(g, c, yrs).then((r) => {
          setScan(r);
          if (r.ok && r.pairs.length) loadDetail(r.pairs[0].a, r.pairs[0].b, yrs);
        }),
        getPairHeatmap(g, yrs).then(setHeatmap).catch(() => {}),
      ])
        .catch((e) => setError(String(e)))
        .finally(() => setScanning(false));
    },
    [loadDetail],
  );

  useEffect(() => { runScan(group, corr, years); }, [group, years, runScan]); // corr applied via button

  if (error)
    return (
      <main className="mx-auto max-w-7xl p-8">
        <div className="rounded-lg border border-red-900 bg-red-950/40 p-4 text-sm text-red-300">
          API nicht erreichbar ({error}). Starte sie mit{" "}
          <code>uvicorn apps.api.main:app --port 8000</code>.
        </div>
      </main>
    );

  return (
    <main className="mx-auto max-w-7xl p-6">
      {/* ── header + controls ──────────────────────────────────── */}
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="flex items-center gap-2 text-3xl font-semibold tracking-tight">
            <span className="text-cyan-300">⇄</span> Statistical Arbitrage Explorer
          </h1>
          <p className="mt-1 text-sm text-zinc-400">
            Kointegrierte Paare · Engle-Granger ADF · Spread-Z-Score · Mean-Reversion
          </p>
        </div>
        <div className="flex flex-wrap items-end gap-3">
          <label className="flex flex-col text-[10px] uppercase tracking-wide text-zinc-500">
            Asset-Gruppe
            <select
              value={group}
              onChange={(e) => setGroup(e.target.value)}
              className="mt-1 rounded-md border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm text-zinc-100"
            >
              {groups.map((g) => (
                <option key={g.id} value={g.id}>
                  {g.label} ({g.n_assets})
                </option>
              ))}
            </select>
          </label>
          <label className="flex flex-col text-[10px] uppercase tracking-wide text-zinc-500">
            Korr-Schwelle: {corr.toFixed(2)}
            <input
              type="range" min={0.5} max={0.95} step={0.05} value={corr}
              onChange={(e) => setCorr(parseFloat(e.target.value))}
              className="mt-2 w-32 accent-cyan-400"
            />
          </label>
          <label className="flex flex-col text-[10px] uppercase tracking-wide text-zinc-500">
            Historie
            <select
              value={years}
              onChange={(e) => setYears(parseInt(e.target.value))}
              className="mt-1 rounded-md border border-zinc-700 bg-zinc-900 px-2 py-2 text-sm text-zinc-100"
            >
              {[3, 5, 6, 8, 10].map((y) => <option key={y} value={y}>{y}J</option>)}
            </select>
          </label>
          <button
            onClick={() => runScan(group, corr, years)}
            disabled={scanning}
            className="rounded-md border border-cyan-600 bg-cyan-500/10 px-4 py-2 text-sm text-cyan-200 hover:border-cyan-400 disabled:opacity-50"
          >
            {scanning ? "scanne…" : "Scan ▸"}
          </button>
        </div>
      </div>

      {/* ── scan funnel summary ────────────────────────────────── */}
      {scan?.ok && (
        <div className="mt-5 flex flex-wrap items-center gap-3 text-xs">
          <Funnel n={scan.n_possible_pairs} label="mögliche Paare" tone="zinc" />
          <span className="text-zinc-600">→</span>
          <Funnel n={scan.stage1_survivors} label={`Korr ≥ ${scan.corr_threshold.toFixed(2)}`} tone="sky" />
          <span className="text-zinc-600">→</span>
          <Funnel n={scan.n_cointegrated} label="kointegriert (ADF p<0.05)" tone="cyan" />
          <span className="text-zinc-600">→</span>
          <Funnel n={scan.n_edges ?? 0} label="echte Edges (OOS bestätigt)" tone="emerald" />
        </div>
      )}

      <div className="mt-5 grid grid-cols-1 gap-5 xl:grid-cols-5">
        {/* ── opportunity list ────────────────────────────────── */}
        <section className="xl:col-span-2">
          <div className="mb-2 text-xs uppercase tracking-widest text-zinc-500">
            Opportunity List · nach |Z| sortiert
          </div>
          <div className="overflow-hidden rounded-xl border border-zinc-800">
            <table className="w-full text-xs">
              <thead className="bg-zinc-900/70 text-[10px] uppercase tracking-wide text-zinc-500">
                <tr>
                  <th className="px-2 py-2 text-left">A / B</th>
                  <th className="px-2 py-2 text-right">ADF p</th>
                  <th className="px-2 py-2 text-right">Half-life</th>
                  <th className="px-2 py-2 text-right">Z</th>
                  <th className="px-2 py-2 text-right" title="Out-of-sample Sharpe des Spread-Backtests">OOS Sh</th>
                  <th className="px-2 py-2 text-right">Edge</th>
                  <th className="px-2 py-2 text-right">Signal</th>
                </tr>
              </thead>
              <tbody>
                {scan?.pairs?.map((p) => (
                  <PairRow key={`${p.a}/${p.b}`} p={p}
                    active={sel?.a === p.a && sel?.b === p.b}
                    onClick={() => loadDetail(p.a, p.b, years)} />
                ))}
                {scan && !scan.ok && (
                  <tr><td colSpan={7} className="px-3 py-6 text-center text-sm text-red-300">
                    Scan fehlgeschlagen: {scan.error ?? "unbekannter Fehler"}
                  </td></tr>
                )}
                {scan?.ok && scan.pairs.length === 0 && (
                  <tr><td colSpan={7} className="px-3 py-6 text-center text-zinc-500">
                    Keine kointegrierten Paare in dieser Gruppe/Fenster.
                  </td></tr>
                )}
              </tbody>
            </table>
          </div>
        </section>

        {/* ── spread / z-score chart ──────────────────────────── */}
        <section className="rounded-xl border border-zinc-800 bg-zinc-900/30 p-4 xl:col-span-3">
          {detail?.ok ? (
            <>
              <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
                <div>
                  <h2 className="text-lg font-semibold text-zinc-100">
                    {detail.a} <span className="text-zinc-500">/</span> {detail.b}
                  </h2>
                  <p className="text-[11px] text-zinc-500">
                    Spread = log({detail.a}) − {detail.stats.hedge_ratio?.toFixed(3)}·log({detail.b}) ·
                    Z-Fenster {detail.z_window}d
                  </p>
                </div>
                <SignalPill signal={detail.stats.signal} z={detail.stats.z_score} />
              </div>
              <SpreadChart data={detail} />
              <div className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-5">
                <Stat label="ADF p-Value" value={fmtP(detail.stats.adf_pvalue)}
                  good={detail.stats.cointegrated} />
                <Stat label="Korrelation" value={detail.stats.correlation?.toFixed(2) ?? "—"} />
                <Stat label="Hedge β" value={detail.stats.hedge_ratio?.toFixed(3) ?? "—"} />
                <Stat label="Half-life" value={fmtHL(detail.stats.half_life)} />
                <Stat label="Z-Score" value={fmtZ(detail.stats.z_score)}
                  good={Math.abs(detail.stats.z_score ?? 0) >= 2} />
              </div>
              {detail.backtest && (
                <div className="mt-5 border-t border-zinc-800 pt-4">
                  <BacktestPanel bt={detail.backtest} />
                </div>
              )}
            </>
          ) : (
            <div className="flex h-[360px] items-center justify-center text-sm text-zinc-500">
              {scanning ? "scanne Gruppe…" : "Wähle ein Paar aus der Liste oder der Heatmap."}
            </div>
          )}
        </section>
      </div>

      {/* ── cointegration heatmap ──────────────────────────────── */}
      <section className="mt-6 rounded-xl border border-zinc-800 bg-zinc-900/30 p-5">
        <div className="mb-3">
          <h2 className="text-sm font-semibold text-zinc-200">
            Cointegration Heatmap · {scan?.label ?? ""}
          </h2>
          <p className="text-[11px] text-zinc-500">
            Farbstärke = 1 − ADF p-Value. Helle Cluster = stark kointegrierte Gruppen. Klick = Paar laden.
          </p>
        </div>
        {heatmap?.ok ? (
          <CointHeatmap data={heatmap} onSelect={(a, b) => loadDetail(a, b, years)} />
        ) : (
          <div className="h-40 animate-pulse rounded-lg bg-zinc-900/60" />
        )}
      </section>
    </main>
  );
}

function PairRow({ p, active, onClick }: { p: PairStat; active: boolean; onClick: () => void }) {
  const badge = SIGNAL_BADGE[p.signal];
  const az = Math.abs(p.z_score ?? 0);
  const bt = p.backtest;
  const oos = bt?.sharpe_oos ?? null;
  return (
    <tr
      onClick={onClick}
      className={cls(
        "cursor-pointer border-t border-zinc-800/70 hover:bg-zinc-800/40",
        active && "bg-cyan-500/10",
      )}
    >
      <td className="px-2 py-2 font-medium text-zinc-200">
        {p.a} <span className="text-zinc-600">/</span> {p.b}
      </td>
      <td className="px-2 py-2 text-right font-mono text-zinc-300">{fmtP(p.adf_pvalue)}</td>
      <td className="px-2 py-2 text-right font-mono text-zinc-400">{fmtHL(p.half_life)}</td>
      <td className={cls("px-2 py-2 text-right font-mono", az >= 2 ? "font-bold text-zinc-50" : "text-zinc-400")}>
        {fmtZ(p.z_score)}
      </td>
      <td className={cls("px-2 py-2 text-right font-mono",
        oos == null ? "text-zinc-500" : oos >= 0.5 ? "text-emerald-300" : oos < 0 ? "text-red-300" : "text-zinc-400")}>
        {oos == null ? "—" : oos.toFixed(2)}
      </td>
      <td className="px-2 py-2 text-right">
        {bt?.is_edge ? (
          <span className="rounded border border-emerald-500 bg-emerald-500/10 px-1.5 py-0.5 text-[10px] font-semibold text-emerald-300">
            EDGE
          </span>
        ) : (
          <span className="text-[10px] text-zinc-600">—</span>
        )}
      </td>
      <td className="px-2 py-2 text-right">
        <span className={cls("rounded border px-1.5 py-0.5 text-[10px]", badge.klass)}>{badge.label}</span>
      </td>
    </tr>
  );
}

function SignalPill({ signal, z }: { signal: PairSignal; z: number | null }) {
  const b = SIGNAL_BADGE[signal];
  const text =
    signal === "long_spread" ? "LONG Spread · kaufe A / verkaufe B"
    : signal === "short_spread" ? "SHORT Spread · verkaufe A / kaufe B"
    : "Neutral · innerhalb ±2σ";
  return (
    <span className={cls("rounded-full border px-3 py-1 text-xs", b.klass)}>
      {text} (Z {fmtZ(z)})
    </span>
  );
}

function Stat({ label, value, good }: { label: string; value: string; good?: boolean }) {
  return (
    <div className="rounded-lg border border-zinc-800 bg-zinc-950/40 p-2.5">
      <div className="text-[9px] uppercase tracking-wide text-zinc-500">{label}</div>
      <div className={cls("mt-0.5 font-mono text-sm", good ? "text-cyan-300" : "text-zinc-200")}>{value}</div>
    </div>
  );
}

function Funnel({ n, label, tone }: { n: number; label: string; tone: "zinc" | "sky" | "cyan" | "emerald" }) {
  const toneCls = {
    zinc: "border-zinc-700 text-zinc-300",
    sky: "border-sky-700 text-sky-300",
    cyan: "border-cyan-500 text-cyan-200",
    emerald: "border-emerald-500 text-emerald-300",
  }[tone];
  return (
    <span className={cls("rounded-lg border px-3 py-1.5", toneCls)}>
      <span className="font-mono text-base font-semibold">{n}</span>{" "}
      <span className="text-[11px] text-zinc-500">{label}</span>
    </span>
  );
}
