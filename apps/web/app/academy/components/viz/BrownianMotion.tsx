"use client";

import { useMemo, useState } from "react";
import { CartesianGrid, ComposedChart, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { AXIS, GRID, gauss, rng, Slider, TOOLTIP, VizFrame } from "./controls";

const N = 200;
const PATHS = 20;

/**
 * Brownian motion as the limit of a random walk: W_t = Σ √dt · Z. Key fact — the spread
 * grows with √t, not t. We draw many driftless paths and overlay the analytical ±2σ√t
 * envelope; ~95% of paths stay inside it. This √t diffusion is the engine of Itō calculus
 * and the dt-vs-√dt asymmetry that makes Black–Scholes work.
 */
export default function BrownianMotion() {
  const [sigma, setSigma] = useState(1);
  const [seed, setSeed] = useState(3);

  const data = useMemo(() => {
    const r = rng(seed * 131 + 5);
    const paths: number[][] = [];
    for (let p = 0; p < PATHS; p++) {
      const w = [0];
      for (let i = 1; i <= N; i++) w.push(w[i - 1] + (sigma / Math.sqrt(N)) * gauss(r));
      paths.push(w);
    }
    return Array.from({ length: N + 1 }, (_, i) => {
      const tt = i / N;
      const env = 2 * sigma * Math.sqrt(tt); // ±2σ√t envelope
      const row: Record<string, number> = { t: +tt.toFixed(3), up: +env.toFixed(3), down: +(-env).toFixed(3) };
      paths.forEach((w, p) => (row[`p${p}`] = +w[i].toFixed(3)));
      return row;
    });
  }, [sigma, seed]);

  return (
    <VizFrame
      caption={
        <>
          {PATHS} driftfreie Pfade. Die gestrichelte Hülle ist <span className="font-mono text-amber-300">±2σ√t</span> —
          die Streuung wächst mit <b>√t</b>, nicht t. ~95% der Pfade bleiben darin. Dieses √t-Diffusionsgesetz
          ist der Kern der Itō-Rechnung und damit von Black–Scholes.
        </>
      }
    >
      <div className="mb-3 flex flex-wrap items-end gap-6">
        <Slider label="Volatilität σ" value={sigma} min={0.3} max={2.5} step={0.1} onChange={setSigma} fmt={(v) => v.toFixed(1)} />
        <button onClick={() => setSeed((s) => s + 1)} className="rounded-md border border-zinc-700 bg-zinc-800 px-3 py-1.5 text-xs text-zinc-200 hover:border-zinc-500">↻ Neu würfeln</button>
      </div>
      <ResponsiveContainer width="100%" height={250}>
        <ComposedChart data={data}>
          <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
          <XAxis dataKey="t" tick={AXIS} type="number" domain={[0, 1]} label={{ value: "Zeit t", fill: "#a1a1aa", fontSize: 10, dy: 12 }} />
          <YAxis tick={AXIS} width={40} domain={[-6, 6]} />
          <Tooltip contentStyle={TOOLTIP} />
          {Array.from({ length: PATHS }, (_, p) => (
            <Line key={p} dataKey={`p${p}`} stroke="#3b82f6" strokeOpacity={0.35} dot={false} strokeWidth={1} isAnimationActive={false} />
          ))}
          <Line dataKey="up" stroke="#eab308" strokeDasharray="5 4" dot={false} strokeWidth={2} isAnimationActive={false} />
          <Line dataKey="down" stroke="#eab308" strokeDasharray="5 4" dot={false} strokeWidth={2} isAnimationActive={false} />
        </ComposedChart>
      </ResponsiveContainer>
    </VizFrame>
  );
}
