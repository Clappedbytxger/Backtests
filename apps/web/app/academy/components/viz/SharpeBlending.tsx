"use client";

import { useMemo, useState } from "react";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { AXIS, GRID, gauss, rng, Slider, TOOLTIP, VizFrame } from "./controls";

const T = 252;
const M = 0.00032; // per-day mean (≈ 0.5 annual Sharpe at S below)
const S = 0.01; // per-day vol

/**
 * Multi-strategy blending — the √N from Module 3 made tradable. Each leg has the same modest
 * Sharpe (~0.5) but the legs share only correlation ρ. Equal-weighting N of them keeps the
 * mean and cuts the vol by √((1+(N−1)ρ)/N), so the blend Sharpe = legSharpe·√(N/(1+(N−1)ρ)).
 * At ρ≈0 a handful of weak legs combine into a strong book (the overlay 0036, Sharpe 1,2+).
 */
export default function SharpeBlending() {
  const [rho, setRho] = useState(0.1);
  const [n, setN] = useState(5);

  const { data, legSharpe, blendSharpe } = useMemo(() => {
    const r = rng(303);
    const legEq = [100];
    const blendEq = [100];
    let le = 1, be = 1;
    const a = Math.sqrt(Math.max(0, rho));
    const b = Math.sqrt(Math.max(0, 1 - rho));
    for (let t = 0; t < T; t++) {
      const common = gauss(r);
      let sum = 0;
      let leg0 = 0;
      for (let i = 0; i < n; i++) {
        const ret = M + S * (a * common + b * gauss(r));
        if (i === 0) leg0 = ret;
        sum += ret;
      }
      const blend = sum / n;
      le *= 1 + leg0;
      be *= 1 + blend;
      legEq.push(+(le * 100).toFixed(2));
      blendEq.push(+(be * 100).toFixed(2));
    }
    const data = legEq.map((v, t) => ({ t, leg: v, blend: blendEq[t] }));
    const legSharpe = (M / S) * Math.sqrt(252);
    const blendVol = S * Math.sqrt((1 + (n - 1) * rho) / n);
    const blendSharpe = (M / blendVol) * Math.sqrt(252);
    return { data, legSharpe, blendSharpe };
  }, [rho, n]);

  return (
    <VizFrame
      caption={
        <>
          {n} Beine, je Sharpe ≈ <b>{legSharpe.toFixed(2)}</b>, Korrelation ρ = {rho.toFixed(2)}. Gleichgewichtet
          ergibt das Blend-Sharpe <b className="text-emerald-400">{blendSharpe.toFixed(2)}</b> — die grüne Kurve
          ist glatter als das einzelne (blaue) Bein bei gleicher Rendite. Stell ρ auf 0 und erhöhe N: der Blend
          skaliert mit √N. Genau so wird aus schwachen Beinen das Overlay-Buch (0036).
        </>
      }
    >
      <div className="mb-3 flex flex-wrap gap-6">
        <Slider label="Korrelation ρ" value={rho} min={0} max={0.9} step={0.05} onChange={setRho} fmt={(v) => v.toFixed(2)} />
        <Slider label="Anzahl Beine N" value={n} min={2} max={12} step={1} onChange={setN} fmt={(v) => String(Math.round(v))} accent="accent-emerald-500" />
      </div>
      <ResponsiveContainer width="100%" height={240}>
        <LineChart data={data}>
          <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
          <XAxis dataKey="t" tick={AXIS} label={{ value: "Handelstage", fill: "#a1a1aa", fontSize: 10, dy: 12 }} />
          <YAxis tick={AXIS} width={42} domain={["auto", "auto"]} />
          <Tooltip contentStyle={TOOLTIP} />
          <Line dataKey="leg" stroke="#3b82f6" dot={false} strokeWidth={1} strokeOpacity={0.7} isAnimationActive={false} name="1 Bein" />
          <Line dataKey="blend" stroke="#22c55e" dot={false} strokeWidth={2} isAnimationActive={false} name="Blend" />
        </LineChart>
      </ResponsiveContainer>
    </VizFrame>
  );
}
