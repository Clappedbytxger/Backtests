"use client";

import { useMemo, useState } from "react";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis, ZAxis } from "recharts";
import { AXIS, GRID, gauss, rng, Slider, TOOLTIP, VizFrame } from "./controls";

/**
 * Two-asset diversification. Left: a scatter of joint returns whose shape is set by
 * the correlation ρ. Right: portfolio volatility √(wᵀΣw) as a function of the weight in
 * asset A. The dip below both single-asset vols is the "free lunch" of diversification —
 * and it vanishes as ρ → 1. Equal vols σ=1 keep the focus on correlation.
 */
export default function CovarianceEllipse() {
  const [rho, setRho] = useState(0.2);

  const scatter = useMemo(() => {
    const r = rng(7);
    const pts = [];
    for (let i = 0; i < 350; i++) {
      const z1 = gauss(r);
      const z2 = gauss(r);
      const x = z1;
      const y = rho * z1 + Math.sqrt(1 - rho * rho) * z2;
      pts.push({ x: +x.toFixed(3), y: +y.toFixed(3) });
    }
    return pts;
  }, [rho]);

  const curve = useMemo(() => {
    // Σ with unit variances and covariance = rho. Portfolio vol over weight w in A.
    const pts = [];
    for (let w = 0; w <= 1.0001; w += 0.05) {
      const v = w * w + (1 - w) * (1 - w) + 2 * w * (1 - w) * rho;
      pts.push({ w: +w.toFixed(2), vol: +Math.sqrt(v).toFixed(3) });
    }
    return pts;
  }, [rho]);

  const minVol = Math.min(...curve.map((c) => c.vol));

  return (
    <VizFrame
      caption={
        <>
          Korrelation ρ = {rho.toFixed(2)}. Links die gemeinsame Punktwolke, rechts die
          Portfolio-Vol <span className="font-mono text-emerald-300">√(wᵀΣw)</span> über dem Gewicht in
          Asset A. Minimum ≈ <b>{minVol.toFixed(2)}</b> — bei ρ&lt;1 <i>unter</i> der Einzel-Vol (=1).
          Das ist Diversifikation; bei ρ→1 verschwindet sie.
        </>
      }
    >
      <div className="mb-3 flex flex-wrap gap-6">
        <Slider label="Korrelation ρ" value={rho} min={-0.9} max={0.99} step={0.01} onChange={setRho} fmt={(v) => v.toFixed(2)} />
      </div>
      <div className="grid gap-4 md:grid-cols-2">
        <ResponsiveContainer width="100%" height={220}>
          <ScatterChart>
            <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
            <XAxis type="number" dataKey="x" domain={[-4, 4]} tick={AXIS} name="Asset A" />
            <YAxis type="number" dataKey="y" domain={[-4, 4]} tick={AXIS} width={32} name="Asset B" />
            <ZAxis range={[12, 12]} />
            <Tooltip contentStyle={TOOLTIP} cursor={{ strokeDasharray: "3 3" }} />
            <Scatter data={scatter} fill="#3b82f6" fillOpacity={0.5} isAnimationActive={false} />
          </ScatterChart>
        </ResponsiveContainer>
        <ResponsiveContainer width="100%" height={220}>
          <LineChart data={curve}>
            <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
            <XAxis dataKey="w" tick={AXIS} label={{ value: "Gewicht A", fill: "#a1a1aa", fontSize: 10, dy: 12 }} />
            <YAxis tick={AXIS} width={36} domain={[0, 1.1]} />
            <Tooltip contentStyle={TOOLTIP} />
            <Line dataKey="vol" stroke="#22c55e" strokeWidth={2} dot={false} isAnimationActive={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </VizFrame>
  );
}
