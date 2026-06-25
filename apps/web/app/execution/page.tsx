"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  getExecBreakdown,
  getExecRadar,
  getExecSimulation,
  getExecUniverse,
  seedExecLedger,
  type ExecBreakdownRow,
  type ExecDemo,
  type ExecRadar,
  type ExecSimulation,
  type LiquidityZone,
} from "@/lib/api";

const cls = (...x: (string | false | undefined)[]) => x.filter(Boolean).join(" ");
const pct = (v: number | null | undefined, d = 1) =>
  v == null ? "—" : `${v >= 0 ? "+" : ""}${(v * 100).toFixed(d)}%`;
const bps = (v: number | null | undefined, d = 1) => (v == null ? "—" : `${v.toFixed(d)} bps`);

const ZONE: Record<LiquidityZone, { color: string; label: string; ring: string }> = {
  safe: { color: "#22c55e", label: "SAFE", ring: "ring-emerald-500/40" },
  caution: { color: "#eab308", label: "CAUTION", ring: "ring-yellow-500/40" },
  warning: { color: "#f97316", label: "WARNING", ring: "ring-orange-500/40" },
  danger: { color: "#ef4444", label: "DANGER", ring: "ring-red-500/40" },
  unknown: { color: "#71717a", label: "N/A", ring: "ring-zinc-600/40" },
};
const COST = { spread: "#3b82f6", impact: "#f59e0b", commission: "#a78bfa", latency: "#f43f5e" };

export default function ExecutionPage() {
  const [universe, setUniverse] = useState<ExecDemo[]>([]);
  const [sel, setSel] = useState<string>("Mean Reversion|IWM");
  const [impactY, setImpactY] = useState(0.5);
  const [sim, setSim] = useState<ExecSimulation | null>(null);
  const [bd, setBd] = useState<ExecBreakdownRow[]>([]);
  const [radar, setRadar] = useState<ExecRadar | null>(null);
  const [loading, setLoading] = useState(false);
  const [seeding, setSeeding] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getExecUniverse().then((r) => setUniverse(r.items)).catch(() => {});
    getExecRadar().then(setRadar).catch(() => {});
  }, []);

  const loadBreakdown = useCallback((y: number) => {
    getExecBreakdown(y).then((r) => setBd(r.rows)).catch(() => {});
  }, []);

  useEffect(() => loadBreakdown(impactY), [impactY, loadBreakdown]);

  useEffect(() => {
    const [strategy, ticker] = sel.split("|");
    setLoading(true);
    setError(null);
    getExecSimulation(strategy, ticker, { impactY })
      .then((r) => {
        if (!r.ok) throw new Error(r.error ?? "unknown");
        setSim(r);
      })
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false));
  }, [sel, impactY]);

  const seed = useCallback(async () => {
    setSeeding(true);
    try {
      const r = await seedExecLedger(60);
      setRadar(r);
      loadBreakdown(impactY);
      const [strategy, ticker] = sel.split("|");
      getExecSimulation(strategy, ticker, { impactY }).then(setSim).catch(() => {});
    } finally {
      setSeeding(false);
    }
  }, [impactY, sel, loadBreakdown]);

  return (
    <main className="mx-auto max-w-7xl px-6 py-6">
      <header className="mb-5 flex flex-wrap items-center gap-3">
        <div>
          <h1 className="text-lg font-semibold tracking-tight">The Execution Desk</h1>
          <p className="text-xs text-zinc-500">
            Adaptive Slippage · Square-Root Market Impact · Implementation Shortfall
          </p>
        </div>
        <div className="ml-auto flex flex-wrap items-center gap-2">
          <select
            value={sel}
            onChange={(e) => setSel(e.target.value)}
            className="rounded border border-zinc-700 bg-zinc-900 px-2 py-1.5 text-xs text-zinc-100"
          >
            {universe.map((d) => (
              <option key={d.key} value={d.key}>
                {d.strategy} · {d.name} ({d.ticker})
              </option>
            ))}
          </select>
          <label className="flex items-center gap-2 rounded border border-zinc-700 bg-zinc-900 px-2 py-1 text-xs text-zinc-400">
            <span>Impact Y</span>
            <input
              type="range"
              min={0}
              max={1.5}
              step={0.1}
              value={impactY}
              onChange={(e) => setImpactY(Number(e.target.value))}
              className="w-24 accent-amber-500"
            />
            <span className="w-6 font-mono tabular-nums text-amber-300">{impactY.toFixed(1)}</span>
          </label>
          <button
            onClick={seed}
            disabled={seeding}
            className={cls(
              "rounded border px-3 py-1.5 text-xs font-medium transition-colors",
              seeding
                ? "border-zinc-700 bg-zinc-800 text-zinc-500"
                : "border-sky-600/60 bg-sky-600/15 text-sky-300 hover:bg-sky-600/25",
            )}
            title="Seed des Implementation-Shortfall-Ledgers mit Beispiel-Fills (Demo)"
          >
            {seeding ? "Seeding …" : "Ledger seeden"}
          </button>
        </div>
      </header>

      {error && (
        <div className="mb-4 rounded-lg border border-red-700/60 bg-red-950/40 px-4 py-2.5 text-sm text-red-300">
          {error}
        </div>
      )}

      {/* top row: gauge + the lie/truth summary */}
      <div className="mb-4 grid grid-cols-1 gap-4 lg:grid-cols-3">
        <LiquidityGauge sim={sim} />
        <div className="lg:col-span-2">
          <TruthSummary sim={sim} loading={loading} />
        </div>
      </div>

      {/* equity curves */}
      <EquityCurves sim={sim} loading={loading} />

      {/* breakdown bars */}
      <SlippageBreakdown rows={bd} />

      {/* post-trade radar */}
      <SlippageRadar radar={radar} />
    </main>
  );
}

// ── liquidity warning gauge (tacho) ────────────────────────────────────────────
function LiquidityGauge({ sim }: { sim: ExecSimulation | null }) {
  const g = sim?.gauge;
  const part = g?.participation ?? 0;
  const zone = (g?.zone ?? "unknown") as LiquidityZone;
  // map participation 0..0.2 (20%) onto a 180° arc, clamped
  const frac = Math.min(1, Math.max(0, part / 0.2));
  const angle = -90 + frac * 180; // degrees, -90 (left) .. +90 (right)
  const R = 80;
  const cx = 100;
  const cy = 100;
  // zone band boundaries as fractions of the 0..20% scale
  const bands: { to: number; color: string }[] = [
    { to: 0.01 / 0.2, color: ZONE.safe.color },
    { to: 0.05 / 0.2, color: ZONE.caution.color },
    { to: 0.1 / 0.2, color: ZONE.warning.color },
    { to: 1, color: ZONE.danger.color },
  ];
  const polar = (f: number, r: number) => {
    const a = (-90 + f * 180) * (Math.PI / 180);
    return [cx + r * Math.cos(a), cy + r * Math.sin(a)];
  };
  const arc = (f0: number, f1: number, r: number) => {
    const [x0, y0] = polar(f0, r);
    const [x1, y1] = polar(f1, r);
    const large = f1 - f0 > 0.5 ? 1 : 0;
    return `M ${x0} ${y0} A ${r} ${r} 0 ${large} 1 ${x1} ${y1}`;
  };
  const [nx, ny] = polar(frac, R - 12);
  const z = ZONE[zone];

  return (
    <section className={cls("rounded-xl border border-zinc-800 bg-zinc-950 p-4 ring-1", z.ring)}>
      <div className="mb-1 flex items-center gap-2">
        <h2 className="text-sm font-semibold">Liquidity Warning</h2>
        <span className="text-[10px] uppercase tracking-widest text-zinc-600">Order vs. ADV</span>
      </div>
      <svg viewBox="0 0 200 120" className="w-full">
        {bands.map((b, i) => {
          const from = i === 0 ? 0 : bands[i - 1].to;
          return (
            <path key={i} d={arc(from, b.to, R)} fill="none" stroke={b.color} strokeWidth={13}
              strokeLinecap="butt" opacity={0.85} />
          );
        })}
        {/* needle */}
        <line x1={cx} y1={cy} x2={nx} y2={ny} stroke={z.color} strokeWidth={3} strokeLinecap="round"
          transform={`rotate(0 ${cx} ${cy})`} />
        <circle cx={cx} cy={cy} r={5} fill={z.color} />
        <text x={cx} y={cy - 28} textAnchor="middle" className="fill-zinc-100"
          style={{ fontSize: 18, fontWeight: 700 }}>
          {g?.participation == null ? "—" : `${(part * 100).toFixed(part < 0.1 ? 2 : 1)}%`}
        </text>
        <text x={cx} y={cy - 12} textAnchor="middle" style={{ fontSize: 8, fill: z.color, fontWeight: 700 }}>
          {z.label}
        </text>
      </svg>
      <p className="mt-1 text-center text-[11px] leading-tight text-zinc-500">{g?.label ?? "—"}</p>
      {sim && (
        <div className="mt-2 flex justify-between text-[10px] text-zinc-600">
          <span>Order: ${(sim.capital / 1e6).toFixed(1)}M</span>
          <span>ADV: ${g && g.dollar_adv ? (g.dollar_adv / 1e6).toFixed(0) : "—"}M</span>
        </div>
      )}
    </section>
  );
}

// ── theoretical vs realized summary ─────────────────────────────────────────────
function TruthSummary({ sim, loading }: { sim: ExecSimulation | null; loading: boolean }) {
  const b = sim?.breakdown;
  const totalCostPct = b ? b.total_cost_return : 0;
  const erosion =
    b && b.gross_total_return ? (totalCostPct / Math.abs(b.gross_total_return)) * 100 : 0;
  return (
    <section className={cls("h-full rounded-xl border border-zinc-800 bg-zinc-950 p-4", loading && "opacity-60")}>
      <div className="mb-3 flex items-center gap-2">
        <h2 className="text-sm font-semibold">Theoretical vs. Realized</h2>
        <span className="text-[10px] uppercase tracking-widest text-zinc-600">die Lüge vs. die Wahrheit</span>
      </div>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Stat label="Brutto-Return (Lüge)" value={pct(b?.gross_total_return)} tone="pos" />
        <Stat
          label="Netto-Return (Wahrheit)"
          value={pct(b?.net_total_return)}
          tone={(b?.net_total_return ?? 0) >= 0 ? "pos" : "neg"}
        />
        <Stat label="Kosten-Drag" value={pct(-totalCostPct)} tone="neg" />
        <Stat label="Rendite vernichtet" value={`${erosion.toFixed(0)}%`} tone="neg" />
      </div>
      <div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-4 border-t border-zinc-800 pt-3">
        <Stat label="Spread" value={bps((b?.spread.return_drag ?? 0) * 1e4 / Math.max(b?.n_trades ?? 1, 1))} sub="/Trade" dot={COST.spread} />
        <Stat label="Market Impact" value={bps((b?.impact.return_drag ?? 0) * 1e4 / Math.max(b?.n_trades ?? 1, 1))} sub="/Trade" dot={COST.impact} />
        <Stat label="Latenz" value={bps(b?.latency_bps)} sub="Ledger" dot={COST.latency} />
        <Stat label="Trades" value={String(b?.n_trades ?? 0)} sub={`Ø Part. ${((b?.avg_participation ?? 0) * 100).toFixed(2)}%`} />
      </div>
    </section>
  );
}

function Stat({ label, value, tone, sub, dot }: { label: string; value: string; tone?: "pos" | "neg"; sub?: string; dot?: string }) {
  return (
    <div>
      <div className="flex items-center gap-1 text-[10px] uppercase tracking-widest text-zinc-600">
        {dot && <span className="h-1.5 w-1.5 rounded-full" style={{ background: dot }} />}
        {label}
      </div>
      <div className={cls("font-mono text-sm tabular-nums", tone === "pos" ? "text-emerald-300" : tone === "neg" ? "text-red-300" : "text-zinc-200")}>
        {value}
      </div>
      {sub && <div className="text-[9px] text-zinc-600">{sub}</div>}
    </div>
  );
}

// ── equity curves ───────────────────────────────────────────────────────────────
function EquityCurves({ sim, loading }: { sim: ExecSimulation | null; loading: boolean }) {
  const data = useMemo(() => {
    if (!sim) return [];
    const real = new Map(sim.equity_realized.map((p) => [p.t, p.v]));
    return sim.equity_theoretical.map((p) => ({
      t: p.t,
      theoretical: p.v,
      realized: real.get(p.t) ?? null,
    }));
  }, [sim]);
  return (
    <section className={cls("mb-4 overflow-hidden rounded-xl border border-zinc-800 bg-zinc-950", loading && "opacity-60")}>
      <div className="flex items-center gap-2 px-4 pt-3">
        <h2 className="text-sm font-semibold">Theoretical vs. Realized Equity</h2>
        <span className="text-[10px] uppercase tracking-widest text-zinc-600">ohne vs. mit Slippage</span>
      </div>
      <div className="px-2 pb-3 pt-1">
        {data.length === 0 ? (
          <div className="py-16 text-center text-xs text-zinc-600">keine Simulation</div>
        ) : (
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={data} margin={{ top: 8, right: 20, bottom: 4, left: 0 }}>
              <CartesianGrid stroke="#27272a" strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey="t" tick={{ fill: "#71717a", fontSize: 10 }} minTickGap={60} axisLine={false} tickLine={false} />
              <YAxis tick={{ fill: "#71717a", fontSize: 10 }} axisLine={false} tickLine={false}
                tickFormatter={(v) => `${v.toFixed(1)}x`} />
              <Tooltip
                contentStyle={{ background: "#18181b", border: "1px solid #3f3f46", borderRadius: 8, fontSize: 12 }}
                labelStyle={{ color: "#a1a1aa" }}
                formatter={(v, n) => [`${Number(v).toFixed(3)}x`, n === "theoretical" ? "Theoretisch" : "Realisiert"]}
              />
              <Legend wrapperStyle={{ fontSize: 11 }}
                formatter={(v) => (v === "theoretical" ? "Theoretisch (ohne Slippage)" : "Realisiert (mit Slippage)")} />
              <Line type="monotone" dataKey="theoretical" stroke="#52525b" strokeWidth={1.6} strokeDasharray="4 3" dot={false} isAnimationActive={false} />
              <Line type="monotone" dataKey="realized" stroke="#22c55e" strokeWidth={1.8} dot={false} isAnimationActive={false} />
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>
    </section>
  );
}

// ── slippage cost breakdown (per strategy/asset) ───────────────────────────────
function SlippageBreakdown({ rows }: { rows: ExecBreakdownRow[] }) {
  const data = useMemo(
    () =>
      rows
        .filter((r) => !r.error)
        .map((r) => ({
          label: r.ticker,
          name: r.name,
          strategy: r.strategy,
          spread: r.spread_bps,
          impact: r.impact_bps,
          commission: r.commission_bps,
          latency: r.latency_bps,
          zone: r.gauge_zone,
        })),
    [rows],
  );
  return (
    <section className="mb-4 overflow-hidden rounded-xl border border-zinc-800 bg-zinc-950">
      <div className="flex items-center gap-2 px-4 pt-3">
        <h2 className="text-sm font-semibold">Slippage Cost Breakdown</h2>
        <span className="text-[10px] uppercase tracking-widest text-zinc-600">bps pro Trade · pro Asset</span>
      </div>
      <div className="px-2 pb-3 pt-1">
        {data.length === 0 ? (
          <div className="py-12 text-center text-xs text-zinc-600">keine Breakdown-Daten</div>
        ) : (
          <ResponsiveContainer width="100%" height={Math.max(260, data.length * 42)}>
            <BarChart data={data} layout="vertical" margin={{ top: 8, right: 24, bottom: 4, left: 8 }} barCategoryGap={12}>
              <CartesianGrid stroke="#27272a" strokeDasharray="3 3" horizontal={false} />
              <XAxis type="number" tick={{ fill: "#71717a", fontSize: 10 }} axisLine={false} tickLine={false} unit=" bps" />
              <YAxis type="category" dataKey="label" width={56} tick={{ fill: "#a1a1aa", fontSize: 11 }} axisLine={false} tickLine={false} />
              <Tooltip
                cursor={{ fill: "#27272a55" }}
                contentStyle={{ background: "#18181b", border: "1px solid #3f3f46", borderRadius: 8, fontSize: 12 }}
                formatter={(v, n) => [`${Number(v).toFixed(2)} bps`, String(n)]}
              />
              <Legend wrapperStyle={{ fontSize: 11 }} />
              <Bar dataKey="spread" stackId="c" fill={COST.spread} name="Spread" isAnimationActive={false} />
              <Bar dataKey="impact" stackId="c" fill={COST.impact} name="Market Impact" isAnimationActive={false} />
              <Bar dataKey="commission" stackId="c" fill={COST.commission} name="Commission" isAnimationActive={false} />
              <Bar dataKey="latency" stackId="c" fill={COST.latency} name="Latenz" radius={[0, 3, 3, 0]} isAnimationActive={false}>
                {data.map((d) => (
                  <Cell key={d.label} fill={COST.latency} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        )}
      </div>
    </section>
  );
}

// ── post-trade slippage radar (Implementation Shortfall) ───────────────────────
function SlippageRadar({ radar }: { radar: ExecRadar | null }) {
  const rows = radar?.by_strategy ?? [];
  return (
    <section className="overflow-hidden rounded-xl border border-zinc-800">
      <div className="flex items-center gap-2 border-b border-zinc-800 bg-zinc-900/60 px-4 py-2.5">
        <h2 className="text-sm font-semibold">Post-Trade Slippage Radar</h2>
        <span className="text-[10px] uppercase tracking-widest text-zinc-600">Implementation Shortfall · Live/Paper-Ledger</span>
        {radar?.n ? <span className="ml-auto text-[10px] text-zinc-600">{radar.n} Fills</span> : null}
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-right text-xs">
          <thead className="bg-zinc-900/40 text-[10px] uppercase tracking-wide text-zinc-500">
            <tr>
              <th className="px-4 py-2 text-left">Strategie</th>
              <th className="px-3 py-2">Fills</th>
              <th className="px-3 py-2">Latenz</th>
              <th className="px-3 py-2">Execution</th>
              <th className="px-3 py-2">Fees</th>
              <th className="px-3 py-2">Total IS</th>
              <th className="px-3 py-2">Ø Latenz (s)</th>
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 && (
              <tr>
                <td colSpan={7} className="px-4 py-8 text-center text-zinc-600">
                  kein Ledger — oben „Ledger seeden" klicken
                </td>
              </tr>
            )}
            {rows.map((r) => (
              <tr key={r.strategy} className="border-b border-zinc-900 hover:bg-zinc-900/50">
                <td className="px-4 py-2 text-left font-medium text-zinc-100">{r.strategy}</td>
                <td className="px-3 py-2 font-mono tabular-nums text-zinc-400">{r.n}</td>
                <td className="px-3 py-2 font-mono tabular-nums" style={{ color: COST.latency }}>{r.latency_bps.toFixed(2)}</td>
                <td className="px-3 py-2 font-mono tabular-nums" style={{ color: COST.impact }}>{r.execution_bps.toFixed(2)}</td>
                <td className="px-3 py-2 font-mono tabular-nums" style={{ color: COST.commission }}>{r.fee_bps.toFixed(2)}</td>
                <td className={cls("px-3 py-2 font-mono tabular-nums font-semibold", r.total_bps >= 0 ? "text-red-300" : "text-emerald-300")}>
                  {r.total_bps >= 0 ? "+" : ""}{r.total_bps.toFixed(2)}
                </td>
                <td className="px-3 py-2 font-mono tabular-nums text-zinc-500">{r.latency_seconds == null ? "—" : r.latency_seconds.toFixed(2)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
