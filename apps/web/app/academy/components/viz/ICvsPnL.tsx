"use client";

import { useMemo, useState } from "react";
import { CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { AXIS, GRID, gauss, rng, Slider, TOOLTIP, VizFrame } from "./controls";

const N = 220; // primary-signal trades

/**
 * Meta-labeling. A primary signal fires many trades; a meta-model scores each with a
 * confidence. Taking ALL trades (grey) drowns the edge in low-confidence noise + cost. Taking
 * only HIGH-confidence trades (green) keeps fewer, better ones — net PnL improves even though
 * the underlying signal's IC is unchanged. This is the 0058/0059 lesson: rank-info ≠ PnL until
 * you size the bet (take it or not), not just predict the direction.
 */
export default function ICvsPnL() {
  const [threshold, setThreshold] = useState(0.6);
  const [costBps, setCostBps] = useState(4);

  const { data, taken, winRate, netAll, netMeta } = useMemo(() => {
    const r = rng(808);
    const cost = costBps;
    const trades = Array.from({ length: N }, () => {
      const c = r(); // meta confidence 0..1
      const ret = 18 * (c - 0.5) + 12 * gauss(r); // bps; higher confidence → higher edge
      return { c, ret };
    });
    let allPnl = 0, metaPnl = 0, taken = 0, wins = 0;
    const data = trades.map((t, i) => {
      allPnl += t.ret - cost;
      if (t.c >= threshold) {
        metaPnl += t.ret - cost;
        taken++;
        if (t.ret - cost > 0) wins++;
      }
      return { i, all: +allPnl.toFixed(1), meta: +metaPnl.toFixed(1) };
    });
    return { data, taken, winRate: taken ? (100 * wins) / taken : 0, netAll: allPnl, netMeta: metaPnl };
  }, [threshold, costBps]);

  return (
    <VizFrame
      caption={
        <>
          <span className="text-zinc-400">Grau</span> = alle {N} Signal-Trades, <span className="text-emerald-400">grün</span> =
          nur die meta-konfidenten ({taken} Trades, Trefferquote {winRate.toFixed(0)} %). Netto: alle{" "}
          <b className={netAll >= 0 ? "text-emerald-400" : "text-red-400"}>{netAll.toFixed(0)} bps</b> vs. meta-gefiltert{" "}
          <b className="text-emerald-400">{netMeta.toFixed(0)} bps</b>. Der Signal-IC ist identisch — Meta-Labeling
          <i> sizet</i> die Wette (nehmen oder nicht) und verwandelt Rang-Info in PnL.
        </>
      }
    >
      <div className="mb-3 flex flex-wrap gap-6">
        <Slider label="Meta-Konfidenz-Schwelle" value={threshold} min={0} max={0.9} step={0.05} onChange={setThreshold} fmt={(v) => v.toFixed(2)} accent="accent-emerald-500" width="w-52" />
        <Slider label="Kosten (bps/Trade)" value={costBps} min={0} max={12} step={0.5} onChange={setCostBps} fmt={(v) => v.toFixed(1)} accent="accent-red-500" />
      </div>
      <ResponsiveContainer width="100%" height={240}>
        <LineChart data={data}>
          <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
          <XAxis dataKey="i" tick={AXIS} label={{ value: "Trade-Nr.", fill: "#a1a1aa", fontSize: 10, dy: 12 }} />
          <YAxis tick={AXIS} width={48} label={{ value: "kum. bps", angle: -90, position: "insideLeft", fill: "#a1a1aa", fontSize: 10 }} />
          <Tooltip contentStyle={TOOLTIP} />
          <ReferenceLine y={0} stroke="#52525b" />
          <Line dataKey="all" stroke="#71717a" dot={false} strokeWidth={1.5} isAnimationActive={false} name="alle Trades" />
          <Line dataKey="meta" stroke="#22c55e" dot={false} strokeWidth={2.5} isAnimationActive={false} name="meta-gefiltert" />
        </LineChart>
      </ResponsiveContainer>
    </VizFrame>
  );
}
