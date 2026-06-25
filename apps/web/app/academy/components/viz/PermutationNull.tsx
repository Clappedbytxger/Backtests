"use client";

import { useMemo, useState } from "react";
import { Bar, CartesianGrid, ComposedChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { AXIS, GRID, gauss, rng, Slider, TOOLTIP, VizFrame } from "./controls";

const PERMS = 1500;
const MIN = -3.5;
const MAX = 3.5;
const BINS = 45;
const W = (MAX - MIN) / BINS;

function sharpe(x: number[]) {
  const m = x.reduce((a, b) => a + b, 0) / x.length;
  const v = Math.max(x.reduce((a, b) => a + (b - m) ** 2, 0) / x.length, 1e-9);
  return m / Math.sqrt(v);
}

/**
 * Permutation test. We build one return series with a tunable real edge, measure its
 * Sharpe, then SHUFFLE the signs/order many times to generate the null distribution
 * "what Sharpe would random timing give?". The p-value is the share of null Sharpes
 * above the observed one. With edge=0 the observed line sits in the middle (p≈0.5).
 */
export default function PermutationNull() {
  const [edge, setEdge] = useState(0.3);
  const [seed, setSeed] = useState(1);
  const n = 120;

  const { bars, observed, p } = useMemo(() => {
    const r = rng(seed * 991 + 7);
    const base = Array.from({ length: n }, () => edge + gauss(r));
    const observed = sharpe(base);
    // null: random sign flips (destroys the directional edge, keeps the distribution)
    const nulls: number[] = [];
    for (let pm = 0; pm < PERMS; pm++) {
      const shuffled = base.map((v) => (r() < 0.5 ? -v : v));
      nulls.push(sharpe(shuffled));
    }
    const p = nulls.filter((s) => s >= observed).length / nulls.length;
    const counts = new Array(BINS).fill(0);
    for (const s of nulls) {
      if (s < MIN || s >= MAX) continue;
      counts[Math.floor((s - MIN) / W)]++;
    }
    const bars = counts.map((c, i) => ({ x: +(MIN + (i + 0.5) * W).toFixed(2), count: c }));
    return { bars, observed, p };
  }, [edge, seed]);

  return (
    <VizFrame
      caption={
        <>
          Graue Verteilung = Sharpe unter Zufalls-Timing (die Nullhypothese). Die grüne Linie ist
          dein beobachteter Sharpe ({observed.toFixed(2)}). p-Wert = Anteil der Null rechts davon ={" "}
          <b className={p < 0.05 ? "text-emerald-400" : "text-amber-400"}>{p.toFixed(3)}</b>. Stell den
          Edge auf 0 — die grüne Linie rutscht in die Mitte, p ≈ 0,5 (kein Signal).
        </>
      }
    >
      <div className="mb-3 flex flex-wrap items-end gap-6">
        <Slider label="wahrer Edge" value={edge} min={0} max={0.6} step={0.02} onChange={setEdge} fmt={(v) => v.toFixed(2)} />
        <button onClick={() => setSeed((s) => s + 1)} className="rounded-md border border-zinc-700 bg-zinc-800 px-3 py-1.5 text-xs text-zinc-200 hover:border-zinc-500">↻ Neue Stichprobe</button>
      </div>
      <ResponsiveContainer width="100%" height={230}>
        <ComposedChart data={bars}>
          <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
          <XAxis dataKey="x" tick={AXIS} type="number" domain={[MIN, MAX]} />
          <YAxis tick={AXIS} width={36} />
          <Tooltip contentStyle={TOOLTIP} />
          <Bar dataKey="count" fill="#71717a" fillOpacity={0.6} isAnimationActive={false} />
          <ReferenceLine x={+observed.toFixed(2)} stroke="#22c55e" strokeWidth={2} />
        </ComposedChart>
      </ResponsiveContainer>
    </VizFrame>
  );
}
