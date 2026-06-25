"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Bar,
  BarChart,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  computeFeatures,
  getFeatureCorrelation,
  getFeatureFactors,
  getFeatureLeakage,
  getFeatureStatus,
  getFeatureTimings,
  getFeatureUniverse,
  type FactorDef,
  type FeatureCorrelation,
  type FeatureGroup,
  type FeatureLeakage,
  type FeatureStatusResponse,
  type FeatureTicker,
  type FeatureTimings,
} from "@/lib/api";

const cls = (...x: (string | false | undefined)[]) => x.filter(Boolean).join(" ");

const GROUP_COLOR: Record<FeatureGroup, string> = {
  momentum: "#60a5fa", // blue
  volatility: "#f59e0b", // amber
  structure: "#34d399", // emerald
};
const GROUP_LABEL: Record<FeatureGroup, string> = {
  momentum: "Momentum",
  volatility: "Volatilität",
  structure: "Struktur",
};

const fmtBytes = (b: number) =>
  b < 1024 ? `${b} B` : b < 1024 * 1024 ? `${(b / 1024).toFixed(1)} KB` : `${(b / 1024 / 1024).toFixed(2)} MB`;

export default function FeaturesPage() {
  const [universe, setUniverse] = useState<FeatureTicker[]>([]);
  const [factors, setFactors] = useState<FactorDef[]>([]);
  const [ticker, setTicker] = useState("SPY");
  const [status, setStatus] = useState<FeatureStatusResponse | null>(null);
  const [corr, setCorr] = useState<FeatureCorrelation | null>(null);
  const [timings, setTimings] = useState<FeatureTimings | null>(null);
  const [leakage, setLeakage] = useState<FeatureLeakage | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getFeatureUniverse().then((r) => setUniverse(r.tickers)).catch(() => {});
    getFeatureFactors().then((r) => setFactors(r.factors)).catch(() => {});
  }, []);

  const loadAll = useCallback((tk: string) => {
    setError(null);
    getFeatureStatus(tk).then(setStatus).catch((e) => setError(String(e)));
    getFeatureCorrelation(tk).then(setCorr).catch(() => setCorr(null));
    getFeatureTimings(tk).then(setTimings).catch(() => setTimings(null));
    getFeatureLeakage(tk).then(setLeakage).catch(() => setLeakage(null));
  }, []);

  useEffect(() => loadAll(ticker), [ticker, loadAll]);

  const recompute = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      const r = await computeFeatures(ticker);
      if (!r.ok) throw new Error(r.error ?? "compute failed");
      loadAll(ticker);
      getFeatureUniverse().then((u) => setUniverse(u.tickers)).catch(() => {});
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }, [ticker, loadAll]);

  const built = useMemo(() => universe.find((u) => u.ticker === ticker)?.built ?? !!status?.count, [universe, ticker, status]);
  const groupOf = useMemo(() => Object.fromEntries(factors.map((f) => [f.name, f.group])), [factors]);

  return (
    <main className="mx-auto max-w-7xl px-6 py-6">
      <header className="mb-5 flex flex-wrap items-center gap-3">
        <div>
          <h1 className="text-lg font-semibold tracking-tight">Feature Health Dashboard</h1>
          <p className="text-xs text-zinc-500">
            ML Feature Store · Parquet + SQLite · look-ahead-safe time-travel
          </p>
        </div>
        <div className="ml-auto flex flex-wrap items-center gap-2">
          <select
            value={ticker}
            onChange={(e) => setTicker(e.target.value)}
            className="rounded border border-zinc-700 bg-zinc-900 px-2 py-1.5 text-xs text-zinc-100"
          >
            {universe.map((u) => (
              <option key={u.ticker} value={u.ticker}>
                {u.name} ({u.ticker}){u.built ? "" : " · nicht gebaut"}
              </option>
            ))}
          </select>
          <button
            onClick={recompute}
            disabled={busy}
            className={cls(
              "rounded border px-3 py-1.5 text-xs font-medium transition-colors",
              busy
                ? "border-zinc-700 bg-zinc-800 text-zinc-500"
                : "border-emerald-600/60 bg-emerald-600/15 text-emerald-300 hover:bg-emerald-600/25",
            )}
          >
            {busy ? "Berechne …" : built ? "Neu berechnen" : "Features bauen"}
          </button>
        </div>
      </header>

      {error && (
        <div className="mb-4 rounded-lg border border-red-700/60 bg-red-950/40 px-4 py-2.5 text-sm text-red-300">
          {error}
        </div>
      )}

      <SummaryBar status={status} leakage={leakage} />

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <CorrelationHeatmap corr={corr} groupOf={groupOf} />
        <TimingsChart timings={timings} />
      </div>

      <RegistryTable status={status} factors={factors} />

      <FactorBuffet factors={factors} />
    </main>
  );
}

// ── summary bar ────────────────────────────────────────────────────────────────
function SummaryBar({ status, leakage }: { status: FeatureStatusResponse | null; leakage: FeatureLeakage | null }) {
  const rows = status?.rows ?? [];
  const stale = status?.stale ?? 0;
  const avgMissing =
    rows.length ? rows.reduce((s, r) => s + r.missing_rate, 0) / rows.length : 0;
  const leakOk = leakage?.ok;
  return (
    <div className="mb-4 flex flex-wrap items-center gap-x-6 gap-y-2 rounded-xl border border-zinc-800 bg-zinc-900/40 px-5 py-3">
      <div
        className={cls(
          "rounded-md border px-3 py-1.5 text-sm font-semibold",
          leakOk == null
            ? "border-zinc-700 bg-zinc-700/20 text-zinc-400"
            : leakOk
              ? "border-emerald-600/50 bg-emerald-500/15 text-emerald-300"
              : "border-red-600/50 bg-red-500/15 text-red-300",
        )}
        title={leakage ? `Shift-Invarianz über ${leakage.n_cutoffs} Stichtage` : undefined}
      >
        {leakOk == null ? "Leakage: —" : leakOk ? "✓ Kein Look-Ahead" : "✗ Leakage erkannt"}
      </div>
      <Metric label="Features" value={String(status?.count ?? 0)} />
      <Metric label="Veraltet" value={String(stale)} tone={stale > 0 ? "warn" : undefined} />
      <Metric label="Ø Missing-Rate" value={`${(avgMissing * 100).toFixed(1)}%`} />
      <Metric label="Größe (Disk)" value={status ? fmtBytes(status.total_disk_bytes) : "—"} />
      {status?.ticker && (
        <span className="ml-auto text-[10px] uppercase tracking-widest text-zinc-600">{status.ticker}</span>
      )}
    </div>
  );
}

function Metric({ label, value, tone }: { label: string; value: string; tone?: "warn" }) {
  return (
    <div>
      <div className="text-[10px] uppercase tracking-widest text-zinc-600">{label}</div>
      <div className={cls("font-mono text-sm tabular-nums", tone === "warn" ? "text-amber-300" : "text-zinc-200")}>
        {value}
      </div>
    </div>
  );
}

// ── correlation heatmap ─────────────────────────────────────────────────────────
function corrColor(v: number | null): string {
  if (v == null) return "#18181b";
  // diverging: red (−1) → zinc (0) → blue (+1)
  const a = Math.min(1, Math.abs(v));
  if (v >= 0) return `rgba(59,130,246,${0.12 + a * 0.78})`;
  return `rgba(239,68,68,${0.12 + a * 0.78})`;
}

function CorrelationHeatmap({
  corr,
  groupOf,
}: {
  corr: FeatureCorrelation | null;
  groupOf: Record<string, string>;
}) {
  const labels = corr?.labels ?? [];
  const n = labels.length;
  return (
    <section className="overflow-hidden rounded-xl border border-zinc-800">
      <div className="flex items-center gap-2 border-b border-zinc-800 bg-zinc-900/60 px-4 py-2.5">
        <h2 className="text-sm font-semibold">Feature-Korrelation</h2>
        <span className="text-[10px] uppercase tracking-widest text-zinc-600">
          redundante Features erkennen
        </span>
        {corr?.n_rows ? (
          <span className="ml-auto text-[10px] text-zinc-600">{corr.n_rows} obs</span>
        ) : null}
      </div>
      <div className="p-4">
        {!corr || !corr.ok || n === 0 ? (
          <div className="py-10 text-center text-xs text-zinc-600">
            {corr?.error ?? "keine Korrelationsdaten — Features bauen"}
          </div>
        ) : (
          <div className="overflow-x-auto">
            <div
              className="grid gap-px"
              style={{ gridTemplateColumns: `minmax(96px,auto) repeat(${n}, minmax(26px, 1fr))` }}
            >
              {/* header row */}
              <div />
              {labels.map((l) => (
                <div
                  key={`h-${l}`}
                  className="flex items-end justify-center pb-1 text-[9px] text-zinc-500"
                  title={l}
                >
                  <span className="origin-bottom-left -rotate-45 whitespace-nowrap" style={{ height: 56 }}>
                    {l}
                  </span>
                </div>
              ))}
              {/* body */}
              {labels.map((row, i) => (
                <Row key={row} row={row} i={i} labels={labels} matrix={corr.matrix} groupOf={groupOf} />
              ))}
            </div>
            <Legend />
          </div>
        )}
      </div>
    </section>
  );
}

function Row({
  row,
  i,
  labels,
  matrix,
  groupOf,
}: {
  row: string;
  i: number;
  labels: string[];
  matrix: (number | null)[][];
  groupOf: Record<string, string>;
}) {
  const g = (groupOf[row] ?? "momentum") as FeatureGroup;
  return (
    <>
      <div className="flex items-center gap-1.5 pr-2 text-[10px] text-zinc-400" title={row}>
        <span className="h-1.5 w-1.5 shrink-0 rounded-full" style={{ background: GROUP_COLOR[g] }} />
        <span className="truncate">{row}</span>
      </div>
      {labels.map((col, j) => {
        const v = matrix[i][j];
        const strong = v != null && i !== j && Math.abs(v) >= 0.8;
        return (
          <div
            key={`${row}-${col}`}
            className={cls("group relative aspect-square", strong && "ring-1 ring-inset ring-white/40")}
            style={{ background: corrColor(v) }}
            title={`${row} × ${col}: ${v == null ? "—" : v.toFixed(2)}`}
          >
            {Math.abs(v ?? 0) >= 0.5 && (
              <span className="absolute inset-0 flex items-center justify-center text-[8px] font-medium tabular-nums text-white/90">
                {v == null ? "" : v.toFixed(1)}
              </span>
            )}
          </div>
        );
      })}
    </>
  );
}

function Legend() {
  return (
    <div className="mt-3 flex items-center gap-2 text-[10px] text-zinc-500">
      <span>−1</span>
      <div className="h-2 w-40 rounded" style={{ background: "linear-gradient(90deg,#ef4444,#27272a,#3b82f6)" }} />
      <span>+1</span>
      <span className="ml-auto inline-flex items-center gap-1">
        <span className="inline-block h-2.5 w-2.5 rounded-sm ring-1 ring-inset ring-white/40" /> |ρ| ≥ 0.8 (redundant)
      </span>
    </div>
  );
}

// ── timings bar chart ────────────────────────────────────────────────────────
function TimingsChart({ timings }: { timings: FeatureTimings | null }) {
  const bars = timings?.bars ?? [];
  return (
    <section className="overflow-hidden rounded-xl border border-zinc-800">
      <div className="flex items-center gap-2 border-b border-zinc-800 bg-zinc-900/60 px-4 py-2.5">
        <h2 className="text-sm font-semibold">Berechnungs-Laufzeit</h2>
        <span className="text-[10px] uppercase tracking-widest text-zinc-600">ms pro Feature</span>
      </div>
      <div className="p-4">
        {bars.length === 0 ? (
          <div className="py-10 text-center text-xs text-zinc-600">
            {timings?.error ?? "keine Timing-Daten — Features bauen"}
          </div>
        ) : (
          <ResponsiveContainer width="100%" height={Math.max(220, bars.length * 30)}>
            <BarChart data={bars} layout="vertical" margin={{ top: 4, right: 40, bottom: 4, left: 8 }}>
              <XAxis type="number" tick={{ fill: "#71717a", fontSize: 10 }} axisLine={false} tickLine={false} unit="ms" />
              <YAxis
                type="category"
                dataKey="factor"
                width={120}
                tick={{ fill: "#a1a1aa", fontSize: 10 }}
                axisLine={false}
                tickLine={false}
              />
              <Tooltip
                cursor={{ fill: "#27272a55" }}
                content={({ active, payload }) =>
                  active && payload?.length ? (
                    <div className="rounded-md border border-zinc-700 bg-zinc-900/95 px-3 py-2 text-xs shadow-lg">
                      <div className="font-mono text-zinc-200">{payload[0].payload.factor}</div>
                      <div className="text-zinc-400">
                        {GROUP_LABEL[payload[0].payload.group as FeatureGroup]} ·{" "}
                        <span className="font-mono text-amber-300">{Number(payload[0].value).toFixed(2)} ms</span>
                      </div>
                    </div>
                  ) : null
                }
              />
              <Bar dataKey="compute_ms" radius={[0, 3, 3, 0]} isAnimationActive={false}>
                {bars.map((b) => (
                  <Cell key={b.factor} fill={GROUP_COLOR[b.group]} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        )}
      </div>
    </section>
  );
}

// ── registry table ──────────────────────────────────────────────────────────
function RegistryTable({
  status,
  factors,
}: {
  status: FeatureStatusResponse | null;
  factors: FactorDef[];
}) {
  const desc = useMemo(() => Object.fromEntries(factors.map((f) => [f.name, f.description])), [factors]);
  const rows = status?.rows ?? [];
  return (
    <section className="mt-4 overflow-hidden rounded-xl border border-zinc-800">
      <div className="flex items-center gap-2 border-b border-zinc-800 bg-zinc-900/60 px-4 py-2.5">
        <h2 className="text-sm font-semibold">Feature Registry</h2>
        <span className="text-[10px] uppercase tracking-widest text-zinc-600">Status · Größe · Missing-Rate</span>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-right text-xs">
          <thead className="bg-zinc-900/40 text-[10px] uppercase tracking-wide text-zinc-500">
            <tr>
              <th className="px-4 py-2 text-left">Feature</th>
              <th className="px-3 py-2 text-left">Gruppe</th>
              <th className="px-3 py-2">Status</th>
              <th className="px-3 py-2">Berechnung</th>
              <th className="px-3 py-2">Rows</th>
              <th className="px-3 py-2">Missing</th>
              <th className="px-3 py-2">Disk</th>
              <th className="px-3 py-2">Alter</th>
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 && (
              <tr>
                <td colSpan={8} className="px-4 py-8 text-center text-zinc-600">
                  keine Features gebaut — oben „Features bauen" klicken
                </td>
              </tr>
            )}
            {rows.map((r) => {
              const g = r.group as FeatureGroup;
              return (
                <tr key={r.factor} className="border-b border-zinc-900 hover:bg-zinc-900/50">
                  <td className="px-4 py-2 text-left">
                    <span className="font-medium text-zinc-100">{r.factor}</span>
                    {desc[r.factor] && (
                      <span className="ml-1.5 hidden text-[10px] text-zinc-600 md:inline">· {desc[r.factor]}</span>
                    )}
                  </td>
                  <td className="px-3 py-2 text-left">
                    <span className="inline-flex items-center gap-1.5 text-zinc-400">
                      <span className="h-1.5 w-1.5 rounded-full" style={{ background: GROUP_COLOR[g] }} />
                      {GROUP_LABEL[g]}
                    </span>
                  </td>
                  <td className="px-3 py-2">
                    <span
                      className={cls(
                        "rounded border px-1.5 py-0.5 text-[10px]",
                        r.status === "up-to-date"
                          ? "border-emerald-600/50 bg-emerald-500/15 text-emerald-300"
                          : "border-amber-600/50 bg-amber-500/15 text-amber-300",
                      )}
                    >
                      {r.status === "up-to-date" ? "up-to-date" : "stale"}
                    </span>
                  </td>
                  <td className="px-3 py-2 font-mono tabular-nums text-zinc-300">{r.compute_ms.toFixed(2)} ms</td>
                  <td className="px-3 py-2 font-mono tabular-nums text-zinc-400">{r.n_rows.toLocaleString()}</td>
                  <td
                    className={cls(
                      "px-3 py-2 font-mono tabular-nums",
                      r.missing_rate > 0.1 ? "text-amber-300" : "text-zinc-400",
                    )}
                  >
                    {(r.missing_rate * 100).toFixed(1)}%
                  </td>
                  <td className="px-3 py-2 font-mono tabular-nums text-zinc-400">{fmtBytes(r.disk_bytes)}</td>
                  <td className="px-3 py-2 font-mono tabular-nums text-zinc-500">{r.age_days.toFixed(1)}d</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}

// ── factor buffet (registry definitions) ────────────────────────────────────
function FactorBuffet({ factors }: { factors: FactorDef[] }) {
  if (factors.length === 0) return null;
  const groups: FeatureGroup[] = ["momentum", "volatility", "structure"];
  return (
    <section className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-3">
      {groups.map((g) => (
        <div key={g} className="rounded-xl border border-zinc-800 bg-zinc-950 p-4">
          <div className="mb-2 flex items-center gap-2">
            <span className="h-2 w-2 rounded-sm" style={{ background: GROUP_COLOR[g] }} />
            <h3 className="text-xs font-semibold text-zinc-200">{GROUP_LABEL[g]}</h3>
          </div>
          <ul className="space-y-1.5">
            {factors.filter((f) => f.group === g).map((f) => (
              <li key={f.name} className="text-[11px] leading-tight">
                <span className="font-mono text-zinc-300">{f.name}</span>
                <span className="block text-zinc-600">{f.description}</span>
              </li>
            ))}
          </ul>
        </div>
      ))}
    </section>
  );
}
