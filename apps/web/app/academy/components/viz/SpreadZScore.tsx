"use client";

import { useMemo, useState } from "react";
import { CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { AXIS, GRID, gauss, rng, Slider, TOOLTIP, VizFrame } from "./controls";

const T = 260;
const WIN = 60; // rolling window for the z-score
const ENTRY = 2;

/**
 * Cointegration & pairs trading. A shared random walk drives two assets, but their SPREAD is
 * a mean-reverting (OU) process: spread_t = φ·spread_{t-1} + ε, with φ = exp(−1/halflife).
 * The rolling z-score crosses ±2 → enter (fade the spread), → 0 → exit. The prices wander,
 * but the spread is stationary — that's the tradable, market-neutral structure (0087 wheat RV).
 */
export default function SpreadZScore() {
  const [halflife, setHalflife] = useState(20);
  const [seed, setSeed] = useState(2);

  const { rows, roundTrips } = useMemo(() => {
    const r = rng(seed * 71 + 3);
    const phi = Math.exp(-1 / halflife);
    const sigma = Math.sqrt(1 - phi * phi);
    const spread: number[] = [0];
    for (let t = 1; t < T; t++) spread.push(phi * spread[t - 1] + sigma * gauss(r));

    const rows: { t: number; z: number }[] = [];
    let inPos = false;
    let roundTrips = 0;
    for (let t = 0; t < T; t++) {
      let z = 0;
      if (t >= WIN) {
        const w = spread.slice(t - WIN, t);
        const m = w.reduce((a, b) => a + b, 0) / WIN;
        const sd = Math.sqrt(w.reduce((a, b) => a + (b - m) ** 2, 0) / WIN) || 1;
        z = (spread[t] - m) / sd;
        if (!inPos && Math.abs(z) >= ENTRY) inPos = true;
        else if (inPos && Math.abs(z) < 0.2) { inPos = false; roundTrips++; }
      }
      rows.push({ t, z: +z.toFixed(3) });
    }
    return { rows, roundTrips };
  }, [halflife, seed]);

  return (
    <VizFrame
      caption={
        <>
          Halbwertszeit {halflife} Tage ⇒ {roundTrips} Mean-Reversion-Trades. Bei |z| ≥ 2 wird der
          Spread gefadet (Entry), bei z → 0 geschlossen (Exit). Kürzere Halbwertszeit ⇒ schnellere,
          häufigere Rückkehr. Die Preise wandern, der <b>Spread ist stationär</b> — das ist die
          marktneutrale, handelbare Struktur (0087 Weizen-RV). Reißt die Kointegration, läuft z davon.
        </>
      }
    >
      <div className="mb-3 flex flex-wrap items-end gap-6">
        <Slider label="Halbwertszeit (Tage)" value={halflife} min={5} max={60} step={1} onChange={setHalflife} fmt={(v) => String(Math.round(v))} />
        <button onClick={() => setSeed((s) => s + 1)} className="rounded-md border border-zinc-700 bg-zinc-800 px-3 py-1.5 text-xs text-zinc-200 hover:border-zinc-500">↻ Neu würfeln</button>
      </div>
      <ResponsiveContainer width="100%" height={240}>
        <LineChart data={rows}>
          <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
          <XAxis dataKey="t" tick={AXIS} />
          <YAxis tick={AXIS} width={36} domain={[-4, 4]} label={{ value: "z-Score", angle: -90, position: "insideLeft", fill: "#a1a1aa", fontSize: 10 }} />
          <Tooltip contentStyle={TOOLTIP} />
          <ReferenceLine y={ENTRY} stroke="#ef4444" strokeDasharray="4 3" label={{ value: "+2 Entry", fill: "#ef4444", fontSize: 10 }} />
          <ReferenceLine y={-ENTRY} stroke="#ef4444" strokeDasharray="4 3" label={{ value: "−2 Entry", fill: "#ef4444", fontSize: 10 }} />
          <ReferenceLine y={0} stroke="#22c55e" strokeDasharray="2 2" />
          <Line dataKey="z" stroke="#3b82f6" dot={false} strokeWidth={1.5} isAnimationActive={false} />
        </LineChart>
      </ResponsiveContainer>
    </VizFrame>
  );
}
