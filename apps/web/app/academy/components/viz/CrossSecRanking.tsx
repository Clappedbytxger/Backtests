"use client";

import { useMemo, useState } from "react";
import { Bar, BarChart, CartesianGrid, Cell, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { AXIS, GRID, gauss, rng, Slider, TOOLTIP, VizFrame } from "./controls";

const N = 14; // assets in the cross-section

/**
 * Cross-sectional ranking portfolio. Each asset has a signal (e.g. 12-1 momentum) and a
 * noisy next-period return correlated with it (so the signal has predictive IC). We rank,
 * go LONG the top quantile and SHORT the bottom (inverse-vol weighted, dollar-neutral). The
 * key lesson (0058): the rank-IC can stay high while the NET hedge return collapses once
 * turnover costs bite — IC ≠ portfolio PnL.
 */
export default function CrossSecRanking() {
  const [quantile, setQuantile] = useState(0.3);
  const [costBps, setCostBps] = useState(15);

  const { bars, ic, gross, net } = useMemo(() => {
    const r = rng(5);
    const assets = Array.from({ length: N }, (_, i) => {
      const signal = gauss(r);
      const vol = 0.8 + 0.6 * Math.abs(gauss(r));
      const ret = 0.22 * signal + 0.7 * gauss(r); // predictive but noisy (small edge vs cost)
      return { i, signal, vol, ret };
    });
    assets.sort((a, b) => b.signal - a.signal);
    const k = Math.max(1, Math.round(quantile * N));
    // inverse-vol weights within each leg, normalised so each leg = 1 unit gross
    const longs = assets.slice(0, k);
    const shorts = assets.slice(N - k);
    const wsum = (xs: typeof assets) => xs.reduce((s, a) => s + 1 / a.vol, 0);
    const lsum = wsum(longs), ssum = wsum(shorts);
    const bars = assets.map((a, rank) => {
      let w = 0;
      if (rank < k) w = (1 / a.vol) / lsum;
      else if (rank >= N - k) w = -(1 / a.vol) / ssum;
      return { name: `#${rank + 1}`, weight: +(w * 100).toFixed(1), ret: a.ret, signal: a.signal };
    });
    // gross hedge return = sum(w * ret); cost = turnover * cost (assume full turnover both legs)
    const gross = bars.reduce((s, b) => s + (b.weight / 100) * b.ret, 0);
    const turnover = 2; // both legs fully traded each rebalance
    const net = gross - turnover * (costBps / 10000) * 100; // scale to comparable units
    // rank-IC: correlation of signal-rank and return (Spearman-ish via Pearson on values)
    const ms = assets.reduce((s, a) => s + a.signal, 0) / N;
    const mr = assets.reduce((s, a) => s + a.ret, 0) / N;
    let cov = 0, vs = 0, vr = 0;
    for (const a of assets) { cov += (a.signal - ms) * (a.ret - mr); vs += (a.signal - ms) ** 2; vr += (a.ret - mr) ** 2; }
    const ic = cov / Math.sqrt(vs * vr);
    return { bars, ic, gross, net };
  }, [quantile, costBps]);

  return (
    <VizFrame
      caption={
        <>
          Assets nach Signal sortiert (#1 = stärkstes). <span className="text-emerald-400">Grün = Long</span>,{" "}
          <span className="text-red-400">Rot = Short</span>, invers-Vol gewichtet, dollar-neutral.
          Rang-IC = <b>{ic.toFixed(2)}</b> (bleibt hoch), aber netto: brutto {gross.toFixed(2)} →{" "}
          <b className={net > 0 ? "text-emerald-400" : "text-red-400"}>netto {net.toFixed(2)}</b> nach Kosten.
          Dreh die Kosten hoch — der IC ändert sich nicht, der PnL kippt. <i>IC ≠ PnL.</i>
        </>
      }
    >
      <div className="mb-3 flex flex-wrap gap-6">
        <Slider label="Quantil je Bein" value={quantile} min={0.1} max={0.5} step={0.05} onChange={setQuantile} fmt={(v) => `${(v * 100).toFixed(0)}%`} />
        <Slider label="Kosten (bps/Seite)" value={costBps} min={0} max={80} step={1} onChange={setCostBps} fmt={(v) => `${Math.round(v)} bps`} accent="accent-red-500" />
      </div>
      <ResponsiveContainer width="100%" height={230}>
        <BarChart data={bars}>
          <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
          <XAxis dataKey="name" tick={{ fill: "#71717a", fontSize: 9 }} />
          <YAxis tick={AXIS} width={40} label={{ value: "Gewicht %", angle: -90, position: "insideLeft", fill: "#a1a1aa", fontSize: 10 }} />
          <Tooltip contentStyle={TOOLTIP} formatter={(v) => `${Number(v).toFixed(1)}%`} />
          <ReferenceLine y={0} stroke="#52525b" />
          <Bar dataKey="weight" isAnimationActive={false}>
            {bars.map((b, i) => (
              <Cell key={i} fill={b.weight >= 0 ? "#22c55e" : "#ef4444"} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </VizFrame>
  );
}
