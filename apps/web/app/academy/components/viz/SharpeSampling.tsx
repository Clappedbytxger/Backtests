"use client";

import { useMemo, useState } from "react";
import { Bar, CartesianGrid, ComposedChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { AXIS, GRID, gauss, rng, Slider, TOOLTIP, VizFrame } from "./controls";

const TRIALS = 2000;
const MIN = -1.5;
const MAX = 2.5;
const BINS = 40;
const W = (MAX - MIN) / BINS;

/**
 * Sampling distribution of the estimated Sharpe. The TRUE per-trade Sharpe is fixed;
 * each "study" draws n trades and estimates Sharpe = mean/std. The histogram shows how
 * wildly the estimate scatters at small n and tightens ∝ 1/√n — the visual proof that
 * 20 seasonal trades cannot pin down an edge.
 */
export default function SharpeSampling() {
  const [n, setN] = useState(20);
  const [trueSharpe, setTrueSharpe] = useState(0.5);

  const { bars, mean, sd } = useMemo(() => {
    const r = rng(123);
    const est: number[] = [];
    for (let t = 0; t < TRIALS; t++) {
      let s = 0;
      let s2 = 0;
      for (let i = 0; i < n; i++) {
        const x = trueSharpe + gauss(r); // per-trade return, unit vol, mean = trueSharpe
        s += x;
        s2 += x * x;
      }
      const m = s / n;
      const v = Math.max(s2 / n - m * m, 1e-9);
      est.push(m / Math.sqrt(v));
    }
    const mean = est.reduce((a, b) => a + b, 0) / est.length;
    const sd = Math.sqrt(est.reduce((a, b) => a + (b - mean) ** 2, 0) / est.length);
    const counts = new Array(BINS).fill(0);
    for (const e of est) {
      if (e < MIN || e >= MAX) continue;
      counts[Math.floor((e - MIN) / W)]++;
    }
    const bars = counts.map((c, i) => ({ x: +(MIN + (i + 0.5) * W).toFixed(2), count: c }));
    return { bars, mean, sd };
  }, [n, trueSharpe]);

  const frac0 = useMemo(() => {
    const r = rng(123);
    let neg = 0;
    for (let t = 0; t < TRIALS; t++) {
      let s = 0, s2 = 0;
      for (let i = 0; i < n; i++) { const x = trueSharpe + gauss(r); s += x; s2 += x * x; }
      const m = s / n; const v = Math.max(s2 / n - m * m, 1e-9);
      if (m / Math.sqrt(v) < 0) neg++;
    }
    return neg / TRIALS;
  }, [n, trueSharpe]);

  return (
    <VizFrame
      caption={
        <>
          Wahres Sharpe pro Trade = {trueSharpe.toFixed(2)}, aber bei n={n} streut die Schätzung
          um ±{sd.toFixed(2)} (∝ 1/√n). In <b>{(frac0 * 100).toFixed(0)}%</b> der Studien wirkt die
          Strategie sogar negativ. Schiebe n hoch — die Verteilung zieht sich zusammen.
        </>
      }
    >
      <div className="mb-3 flex flex-wrap gap-6">
        <Slider label="n (Trades)" value={n} min={5} max={300} step={5} onChange={setN} fmt={(v) => String(Math.round(v))} />
        <Slider label="wahres Sharpe/Trade" value={trueSharpe} min={0} max={1.5} step={0.05} onChange={setTrueSharpe} fmt={(v) => v.toFixed(2)} />
      </div>
      <ResponsiveContainer width="100%" height={230}>
        <ComposedChart data={bars}>
          <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
          <XAxis dataKey="x" tick={AXIS} type="number" domain={[MIN, MAX]} />
          <YAxis tick={AXIS} width={36} />
          <Tooltip contentStyle={TOOLTIP} />
          <Bar dataKey="count" fill="#3b82f6" fillOpacity={0.6} isAnimationActive={false} />
          <ReferenceLine x={0} stroke="#ef4444" strokeDasharray="4 3" label={{ value: "0", fill: "#ef4444", fontSize: 11 }} />
          <ReferenceLine x={+mean.toFixed(2)} stroke="#22c55e" strokeDasharray="4 3" />
        </ComposedChart>
      </ResponsiveContainer>
    </VizFrame>
  );
}
