"use client";

import { useMemo, useState } from "react";
import {
  Area,
  ComposedChart,
  Line,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

/** Standard-normal PDF with mean mu and standard deviation sigma. */
function normalPdf(x: number, mu: number, sigma: number) {
  const z = (x - mu) / sigma;
  return Math.exp(-0.5 * z * z) / (sigma * Math.sqrt(2 * Math.PI));
}

/**
 * Interactive normal distribution: drag mu (Lage) and sigma (Streuung) and watch
 * the bell curve shift and widen. The shaded band is ±1σ (~68% of the mass) —
 * the visual anchor for "Volatilität = σ der Returns".
 */
export default function NormalDistribution() {
  const [mu, setMu] = useState(0);
  const [sigma, setSigma] = useState(1);

  const data = useMemo(() => {
    const pts = [];
    for (let x = -6; x <= 6; x += 0.1) {
      const y = normalPdf(x, mu, sigma);
      const inBand = x >= mu - sigma && x <= mu + sigma;
      pts.push({ x: +x.toFixed(2), y, band: inBand ? y : 0 });
    }
    return pts;
  }, [mu, sigma]);

  return (
    <div className="rounded-lg border border-zinc-800 bg-zinc-900/40 p-4">
      <div className="mb-3 flex flex-wrap gap-6">
        <Slider label="μ (Mittelwert)" value={mu} min={-3} max={3} step={0.1} onChange={setMu} />
        <Slider label="σ (Standardabw.)" value={sigma} min={0.3} max={3} step={0.1} onChange={setSigma} />
      </div>
      <ResponsiveContainer width="100%" height={240}>
        <ComposedChart data={data}>
          <XAxis dataKey="x" tick={{ fill: "#a1a1aa", fontSize: 11 }} type="number" domain={[-6, 6]} />
          <YAxis tick={{ fill: "#a1a1aa", fontSize: 11 }} width={36} />
          <Tooltip
            contentStyle={{ background: "#18181b", border: "1px solid #3f3f46" }}
            formatter={(v) => Number(v).toFixed(3)}
            labelFormatter={(l) => `x = ${l}`}
          />
          <Area dataKey="band" stroke="none" fill="#3b82f6" fillOpacity={0.25} isAnimationActive={false} />
          <Line dataKey="y" stroke="#3b82f6" dot={false} strokeWidth={2} isAnimationActive={false} />
          <ReferenceLine x={mu} stroke="#eab308" strokeDasharray="4 3" />
        </ComposedChart>
      </ResponsiveContainer>
      <p className="mt-2 text-xs text-zinc-500">
        Blaue Fläche = ±1σ ≈ 68% der Wahrscheinlichkeitsmasse. Größeres σ ⇒ breitere Glocke
        ⇒ riskanter. Das ist die Mathe hinter „annualisierte Volatilität“.
      </p>
    </div>
  );
}

function Slider({
  label,
  value,
  min,
  max,
  step,
  onChange,
}: {
  label: string;
  value: number;
  min: number;
  max: number;
  step: number;
  onChange: (v: number) => void;
}) {
  return (
    <label className="flex flex-col text-xs text-zinc-400">
      <span className="mb-1">
        {label}: <span className="font-mono text-zinc-200">{value.toFixed(1)}</span>
      </span>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(parseFloat(e.target.value))}
        className="w-44 accent-blue-500"
      />
    </label>
  );
}
