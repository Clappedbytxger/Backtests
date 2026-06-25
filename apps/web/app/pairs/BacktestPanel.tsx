"use client";

import { useMemo } from "react";
import {
  Area,
  CartesianGrid,
  ComposedChart,
  ReferenceArea,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { PairBacktest } from "@/lib/api";

const cls = (...x: (string | false | undefined)[]) => x.filter(Boolean).join(" ");
const pct = (x: number | null) => (x == null ? "—" : `${x >= 0 ? "+" : ""}${(x * 100).toFixed(1)}%`);
const num = (x: number | null, d = 2) => (x == null ? "—" : x.toFixed(d));

/**
 * Net-of-cost spread-reversion backtest panel: the equity curve (with the
 * IS/OOS split shaded) plus the verdict — is this cointegrated pair an actual
 * tradable EDGE, or just a statistical artefact?
 */
export default function BacktestPanel({ bt }: { bt: PairBacktest }) {
  const rows = useMemo(
    () => (bt.curve ?? []).map((p, i) => ({ i, t: p.t, equity: (p.equity - 1) * 100 })),
    [bt.curve],
  );
  const splitIdx = useMemo(() => {
    if (!bt.split_date) return -1;
    const k = rows.findIndex((r) => r.t >= bt.split_date!);
    return k < 0 ? Math.floor(rows.length * (bt.split_index_frac ?? 0.7)) : k;
  }, [rows, bt.split_date, bt.split_index_frac]);

  const tickFmt = (i: number) => rows[i]?.t?.slice(0, 7) ?? "";

  return (
    <div>
      <div className="mb-2 flex items-center justify-between">
        <span className="text-xs uppercase tracking-widest text-zinc-500">
          Spread-Reversion-Backtest (netto Kosten {num(bt.cost_bps, 0)} bps/Leg)
        </span>
        <EdgeBadge isEdge={bt.is_edge} />
      </div>

      <ResponsiveContainer width="100%" height={170}>
        <ComposedChart data={rows} margin={{ top: 6, right: 12, left: -10, bottom: 0 }}>
          {splitIdx > 0 && (
            <ReferenceArea x1={splitIdx} x2={rows.length - 1} fill="#22d3ee" fillOpacity={0.06} stroke="none" />
          )}
          <CartesianGrid stroke="#27272a" strokeDasharray="2 4" vertical={false} />
          <XAxis dataKey="i" type="number" domain={[0, rows.length - 1]} tickFormatter={tickFmt}
            tick={{ fill: "#71717a", fontSize: 9 }} minTickGap={50} stroke="#3f3f46" />
          <YAxis tick={{ fill: "#71717a", fontSize: 9 }} stroke="#3f3f46" width={40}
            tickFormatter={(v) => (typeof v === "number" ? `${v.toFixed(0)}%` : v)} />
          <ReferenceLine y={0} stroke="#52525b" strokeDasharray="3 3" />
          {splitIdx > 0 && (
            <ReferenceLine x={splitIdx} stroke="#22d3ee" strokeDasharray="4 3" strokeOpacity={0.7}
              label={{ value: "OOS", position: "insideTopRight", fill: "#22d3ee", fontSize: 9 }} />
          )}
          <Tooltip
            contentStyle={{ background: "#09090b", border: "1px solid #27272a", borderRadius: 8, fontSize: 11 }}
            labelStyle={{ color: "#a1a1aa" }}
            formatter={((v: unknown) => [typeof v === "number" ? `${v.toFixed(1)}%` : String(v), "kum. Spread-PnL"]) as never}
            labelFormatter={((i: unknown) => rows[Number(i)]?.t ?? "") as never}
          />
          <Area dataKey="equity" stroke="#22d3ee" fill="#22d3ee" fillOpacity={0.12} strokeWidth={1.5} isAnimationActive={false} />
        </ComposedChart>
      </ResponsiveContainer>

      <div className="mt-3 grid grid-cols-3 gap-2 sm:grid-cols-6">
        <BtStat label="Sharpe IS" value={num(bt.sharpe_is)} />
        <BtStat label="Sharpe OOS" value={num(bt.sharpe_oos)} good={(bt.sharpe_oos ?? 0) >= 0.5}
          bad={(bt.sharpe_oos ?? 0) < 0} />
        <BtStat label="Kum. PnL" value={pct(bt.total_return)} good={(bt.total_return ?? 0) > 0} />
        <BtStat label="OOS-PnL" value={pct(bt.oos_return)} good={(bt.oos_return ?? 0) > 0}
          bad={(bt.oos_return ?? 0) < 0} />
        <BtStat label="Max DD" value={pct(bt.max_drawdown)} bad />
        <BtStat label="Trades / Win" value={`${bt.n_trades} / ${bt.win_rate != null ? (bt.win_rate * 100).toFixed(0) + "%" : "—"}`} />
      </div>
      <p className="mt-2 text-[10px] text-zinc-600">
        β auf In-Sample gefittet und auf OOS angewandt · Z-Score rollierend (kausal) · Position +1 Bar verzögert.
        Die OOS-Sharpe entscheidet, ob aus „kointegriert" ein handelbarer Edge wird.
      </p>
    </div>
  );
}

export function EdgeBadge({ isEdge }: { isEdge: boolean }) {
  return isEdge ? (
    <span className="rounded-full border border-emerald-500 bg-emerald-500/15 px-2.5 py-0.5 text-[11px] font-semibold text-emerald-300">
      ✓ EDGE (OOS bestätigt)
    </span>
  ) : (
    <span className="rounded-full border border-zinc-600 bg-zinc-800/50 px-2.5 py-0.5 text-[11px] text-zinc-400">
      kein Edge (kointegriert, aber netto/OOS schwach)
    </span>
  );
}

function BtStat({ label, value, good, bad }: { label: string; value: string; good?: boolean; bad?: boolean }) {
  return (
    <div className="rounded-lg border border-zinc-800 bg-zinc-950/40 p-2">
      <div className="text-[9px] uppercase tracking-wide text-zinc-500">{label}</div>
      <div className={cls("mt-0.5 font-mono text-sm",
        good ? "text-emerald-300" : bad ? "text-red-300" : "text-zinc-200")}>
        {value}
      </div>
    </div>
  );
}
