"use client";

import { useMemo, useState } from "react";
import { Area, CartesianGrid, ComposedChart, Line, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { AXIS, GRID, Slider, TOOLTIP, VizFrame } from "./controls";

/**
 * The volatility smile and the variance risk premium. Implied vol is not flat across strikes:
 * out-of-the-money puts trade richer (skew) because crash insurance is in demand. Realised vol
 * is the flat dashed line. The shaded gap between the ATM implied and realised is the VRP — the
 * premium option SELLERS earn (0054). But selling it is short-gamma: the left tail is where the
 * −34 % day lives (0056), which is why it must be harvested with defined risk.
 */
export default function VolSmile() {
  const [atmIv, setAtmIv] = useState(0.2);
  const [skew, setSkew] = useState(0.6);
  const [realized, setRealized] = useState(0.15);

  const data = useMemo(() => {
    const pts = [];
    for (let k = 80; k <= 120; k += 1) {
      const m = (100 - k) / 20; // moneyness: +ve for downside strikes
      const iv = atmIv + skew * 0.12 * m + 0.06 * m * m; // skew (linear) + smile (quad)
      pts.push({ k, iv: +(iv * 100).toFixed(2), rv: +(realized * 100).toFixed(2), vrp: +(Math.max(iv - realized, 0) * 100).toFixed(2) });
    }
    return pts;
  }, [atmIv, skew, realized]);

  const vrpAtm = (atmIv - realized) * 100;

  return (
    <VizFrame
      caption={
        <>
          <span className="text-blue-300">Implizite Vol</span> über Strike — OTM-Puts (links) teurer (Skew =
          Crash-Versicherung). <span className="text-zinc-400">Realisierte Vol</span> flach gestrichelt. Die
          Fläche dazwischen ist die <b className="text-emerald-400">VRP</b> (ATM ≈ {vrpAtm.toFixed(1)} Vol-Punkte) —
          was Verkäufer ernten. Aber Short-Vol ist short Gamma: der linke Tail (der −34 %-Tag, 0056) verlangt
          definierte Risiken.
        </>
      }
    >
      <div className="mb-3 flex flex-wrap gap-6">
        <Slider label="ATM implizite Vol" value={atmIv} min={0.1} max={0.5} step={0.01} onChange={setAtmIv} fmt={(v) => `${(v * 100).toFixed(0)}%`} accent="accent-blue-500" />
        <Slider label="Skew" value={skew} min={0} max={1.5} step={0.05} onChange={setSkew} fmt={(v) => v.toFixed(2)} />
        <Slider label="Realisierte Vol" value={realized} min={0.05} max={0.4} step={0.01} onChange={setRealized} fmt={(v) => `${(v * 100).toFixed(0)}%`} accent="accent-zinc-500" />
      </div>
      <ResponsiveContainer width="100%" height={240}>
        <ComposedChart data={data}>
          <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
          <XAxis dataKey="k" tick={AXIS} label={{ value: "Strike", fill: "#a1a1aa", fontSize: 10, dy: 12 }} />
          <YAxis tick={AXIS} width={42} label={{ value: "Vol %", angle: -90, position: "insideLeft", fill: "#a1a1aa", fontSize: 10 }} />
          <Tooltip contentStyle={TOOLTIP} formatter={(v) => `${Number(v).toFixed(1)}%`} />
          <ReferenceLine x={100} stroke="#52525b" strokeDasharray="3 3" label={{ value: "ATM", fill: "#a1a1aa", fontSize: 10 }} />
          <Area dataKey="iv" stroke="none" fill="#3b82f6" fillOpacity={0.12} isAnimationActive={false} />
          <Line dataKey="iv" stroke="#3b82f6" dot={false} strokeWidth={2} isAnimationActive={false} />
          <Line dataKey="rv" stroke="#a1a1aa" dot={false} strokeWidth={1.5} strokeDasharray="5 4" isAnimationActive={false} />
        </ComposedChart>
      </ResponsiveContainer>
    </VizFrame>
  );
}
