"use client";

import { useMemo, useState } from "react";
import { CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { AXIS, GRID, Slider, TOOLTIP, VizFrame } from "./controls";

/**
 * Kelly criterion for a binary bet: maximise expected log-growth
 * g(f) = p·ln(1 + b·f) + (1−p)·ln(1 − f). The peak f* = p − (1−p)/b is the growth-optimal
 * fraction. Note the curve is steep past the peak and goes NEGATIVE before f=1: over-betting
 * destroys capital. That asymmetry (+ estimation error in p) is why pros bet fractional Kelly.
 */
export default function KellyCurve() {
  const [p, setP] = useState(0.55);
  const [b, setB] = useState(1.0);

  const { curve, fStar, gStar } = useMemo(() => {
    const fStar = Math.max(0, p - (1 - p) / b);
    const curve = [];
    for (let f = 0; f <= 0.999; f += 0.01) {
      const g = p * Math.log(1 + b * f) + (1 - p) * Math.log(1 - f);
      curve.push({ f: +f.toFixed(2), g: +g.toFixed(4), half: +(f <= fStar ? g : NaN) });
    }
    const gStar = p * Math.log(1 + b * fStar) + (1 - p) * Math.log(1 - fStar);
    return { curve, fStar, gStar };
  }, [p, b]);

  return (
    <VizFrame
      caption={
        <>
          Optimaler Einsatz <b>f* = {(fStar * 100).toFixed(0)}%</b> des Kapitals (max. log-Wachstum
          {" "}{gStar.toFixed(3)}). Rechts vom Peak fällt die Kurve steil und wird negativ — Überwetten
          ruiniert. Weil p in der Praxis nur <i>geschätzt</i> ist, handelt man meist ½·f* (Fractional Kelly).
        </>
      }
    >
      <div className="mb-3 flex flex-wrap gap-6">
        <Slider label="Trefferquote p" value={p} min={0.35} max={0.8} step={0.01} onChange={setP} fmt={(v) => `${(v * 100).toFixed(0)}%`} />
        <Slider label="Payoff-Verhältnis b" value={b} min={0.3} max={3} step={0.1} onChange={setB} fmt={(v) => `${v.toFixed(1)}:1`} />
      </div>
      <ResponsiveContainer width="100%" height={240}>
        <LineChart data={curve}>
          <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
          <XAxis dataKey="f" tick={AXIS} label={{ value: "Einsatz-Anteil f", fill: "#a1a1aa", fontSize: 10, dy: 12 }} />
          <YAxis tick={AXIS} width={44} domain={[-0.2, "auto"]} />
          <Tooltip contentStyle={TOOLTIP} />
          <ReferenceLine y={0} stroke="#52525b" />
          <ReferenceLine x={+fStar.toFixed(2)} stroke="#22c55e" strokeDasharray="4 3" label={{ value: "f*", fill: "#22c55e", fontSize: 11 }} />
          <Line dataKey="g" stroke="#3b82f6" dot={false} strokeWidth={2} isAnimationActive={false} />
        </LineChart>
      </ResponsiveContainer>
    </VizFrame>
  );
}
