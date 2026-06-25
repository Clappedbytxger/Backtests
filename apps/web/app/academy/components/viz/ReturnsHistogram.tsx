"use client";

import { useMemo, useState } from "react";
import {
  Bar,
  CartesianGrid,
  ComposedChart,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

function gauss(rand: () => number) {
  const u1 = Math.max(rand(), 1e-9);
  return Math.sqrt(-2 * Math.log(u1)) * Math.cos(2 * Math.PI * rand());
}
function rng(seed: number) {
  let a = seed;
  return () => {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
function normalPdf(x: number, sigma: number) {
  return Math.exp(-0.5 * (x / sigma) ** 2) / (sigma * Math.sqrt(2 * Math.PI));
}

const MIN = -6;
const MAX = 6;
const BINS = 49;
const W = (MAX - MIN) / BINS;
const SAMPLES = 4000;

/**
 * Real returns are fat-tailed. We sample a Student-t-like variable (Gaussian scaled
 * by a heavier factor as df shrinks) and overlay the Normal PDF that has the SAME
 * standard deviation. As df drops, the histogram grows fat tails the bell curve
 * cannot see — the visual root of the metrics.py kurtosis/skew warning.
 */
export default function ReturnsHistogram() {
  const [df, setDf] = useState(3); // degrees of freedom; low = fat tails

  const { bars, sigma } = useMemo(() => {
    const r = rng(42);
    const xs: number[] = [];
    for (let i = 0; i < SAMPLES; i++) {
      // crude t: z / sqrt(chi2/df); approximate chi2 by averaging squared gaussians
      let chi = 0;
      for (let k = 0; k < df; k++) chi += gauss(r) ** 2;
      const t = gauss(r) / Math.sqrt(chi / df || 1);
      xs.push(t);
    }
    const mean = xs.reduce((a, b) => a + b, 0) / xs.length;
    const variance = xs.reduce((a, b) => a + (b - mean) ** 2, 0) / xs.length;
    const sd = Math.sqrt(variance);

    const counts = new Array(BINS).fill(0);
    for (const x of xs) {
      if (x < MIN || x >= MAX) continue;
      counts[Math.floor((x - MIN) / W)]++;
    }
    const bars = counts.map((c, i) => {
      const center = MIN + (i + 0.5) * W;
      return {
        x: +center.toFixed(2),
        density: c / SAMPLES / W, // empirical density
        normal: normalPdf(center, sd), // same-σ normal overlay
      };
    });
    return { bars, sigma: sd };
  }, [df]);

  return (
    <div className="rounded-lg border border-zinc-800 bg-zinc-900/40 p-4">
      <div className="mb-3 flex flex-wrap items-end gap-6">
        <label className="flex flex-col text-xs text-zinc-400">
          <span className="mb-1">
            Freiheitsgrade df: <span className="font-mono text-zinc-200">{df}</span>{" "}
            <span className="text-zinc-600">(klein = fette Tails)</span>
          </span>
          <input
            type="range"
            min={1}
            max={30}
            step={1}
            value={df}
            onChange={(e) => setDf(parseInt(e.target.value))}
            className="w-52 accent-red-500"
          />
        </label>
        <div className="text-xs text-zinc-500">
          empirisches σ ≈ <span className="font-mono text-zinc-300">{sigma.toFixed(2)}</span>
        </div>
      </div>
      <ResponsiveContainer width="100%" height={240}>
        <ComposedChart data={bars}>
          <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
          <XAxis dataKey="x" tick={{ fill: "#a1a1aa", fontSize: 11 }} type="number" domain={[MIN, MAX]} />
          <YAxis tick={{ fill: "#a1a1aa", fontSize: 11 }} width={36} />
          <Tooltip
            contentStyle={{ background: "#18181b", border: "1px solid #3f3f46" }}
            formatter={(v) => Number(v).toFixed(3)}
          />
          <Bar dataKey="density" fill="#ef4444" fillOpacity={0.5} isAnimationActive={false} />
          <Line dataKey="normal" stroke="#3b82f6" dot={false} strokeWidth={2} isAnimationActive={false} />
        </ComposedChart>
      </ResponsiveContainer>
      <p className="mt-2 text-xs text-zinc-500">
        Rot = simulierte Returns, Blau = Normalverteilung mit <em>gleichem σ</em>. Bei kleinem df
        ragen die Enden („Tails“) weit über die blaue Kurve hinaus — das sind die Crash-Tage, die
        ein reines σ/Sharpe-Maß unterschätzt (siehe 0054 VIX-Carry: −34% an einem Tag).
      </p>
    </div>
  );
}
