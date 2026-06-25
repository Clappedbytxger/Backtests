"use client";

import { useMemo, useState } from "react";
import { CartesianGrid, ComposedChart, Line, ResponsiveContainer, Scatter, Tooltip, XAxis, YAxis, ZAxis } from "recharts";
import { AXIS, GRID, gauss, rng, Slider, TOOLTIP, VizFrame } from "./controls";

/**
 * OLS of strategy returns on market returns: r_strat = α + β·r_mkt + ε. Sliders set the
 * TRUE β (market exposure) and α (skill), plus noise. The fitted line + estimates show
 * how regression separates real alpha from hidden beta — the 0015 "is my overlay just
 * long beta?" question made visual. R² = share of variance explained by the market.
 */
export default function RegressionFit() {
  const [beta, setBeta] = useState(0.6);
  const [alpha, setAlpha] = useState(0.0);
  const [noise, setNoise] = useState(0.8);

  const { points, fit, bHat, aHat, r2 } = useMemo(() => {
    const r = rng(11);
    const xs: number[] = [];
    const ys: number[] = [];
    for (let i = 0; i < 200; i++) {
      const x = gauss(r); // market return
      const y = alpha + beta * x + noise * gauss(r);
      xs.push(x);
      ys.push(y);
    }
    const mx = xs.reduce((a, b) => a + b, 0) / xs.length;
    const my = ys.reduce((a, b) => a + b, 0) / ys.length;
    let sxy = 0, sxx = 0, syy = 0;
    for (let i = 0; i < xs.length; i++) {
      sxy += (xs[i] - mx) * (ys[i] - my);
      sxx += (xs[i] - mx) ** 2;
      syy += (ys[i] - my) ** 2;
    }
    const bHat = sxy / sxx;
    const aHat = my - bHat * mx;
    const r2 = (sxy * sxy) / (sxx * syy);
    const points = xs.map((x, i) => ({ x: +x.toFixed(3), y: +ys[i].toFixed(3) }));
    const fit = [-4, 4].map((x) => ({ x, yfit: aHat + bHat * x }));
    return { points, fit, bHat, aHat, r2 };
  }, [beta, alpha, noise]);

  const merged = [...points.map((p) => ({ ...p })), ...fit.map((f) => ({ ...f }))];

  return (
    <VizFrame
      caption={
        <>
          Geschätztes <b>β = {bHat.toFixed(2)}</b> (Marktexposure), <b>α = {aHat.toFixed(2)}</b> (Skill),
          R² = {(r2 * 100).toFixed(0)}%. Erhöhe das Rauschen ⇒ α wird unschärfer; setze α=0 ⇒ die Strategie
          ist <i>reines</i> Beta. Genau diese Regression trennt echtes Alpha von verstecktem Long-Beta.
        </>
      }
    >
      <div className="mb-3 flex flex-wrap gap-6">
        <Slider label="wahres β" value={beta} min={-1} max={1.5} step={0.05} onChange={setBeta} fmt={(v) => v.toFixed(2)} />
        <Slider label="wahres α" value={alpha} min={-1} max={1} step={0.05} onChange={setAlpha} fmt={(v) => v.toFixed(2)} accent="accent-emerald-500" />
        <Slider label="Rauschen σ(ε)" value={noise} min={0.1} max={2} step={0.1} onChange={setNoise} fmt={(v) => v.toFixed(1)} accent="accent-red-500" />
      </div>
      <ResponsiveContainer width="100%" height={240}>
        <ComposedChart data={merged}>
          <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
          <XAxis type="number" dataKey="x" domain={[-4, 4]} tick={AXIS} label={{ value: "Markt-Return", fill: "#a1a1aa", fontSize: 10, dy: 12 }} />
          <YAxis type="number" dataKey="y" domain={[-5, 5]} tick={AXIS} width={36} />
          <ZAxis range={[14, 14]} />
          <Tooltip contentStyle={TOOLTIP} cursor={{ strokeDasharray: "3 3" }} />
          <Scatter data={points} fill="#3b82f6" fillOpacity={0.45} isAnimationActive={false} />
          <Line data={fit} dataKey="yfit" stroke="#22c55e" strokeWidth={2} dot={false} isAnimationActive={false} />
        </ComposedChart>
      </ResponsiveContainer>
    </VizFrame>
  );
}
