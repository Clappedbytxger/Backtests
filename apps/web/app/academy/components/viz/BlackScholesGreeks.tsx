"use client";

import { useMemo, useState } from "react";
import { CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { AXIS, GRID, normalCdf, normalPdf, Slider, TOOLTIP, VizFrame } from "./controls";

const K = 100; // strike fixed; vary spot on the x-axis

/**
 * Black–Scholes call price and its Greeks across spot. Delta = N(d1) is the hedge ratio
 * (slope of price vs spot); Gamma = N'(d1)/(S·σ·√T) peaks at the money — that curvature is
 * what option sellers are short. Cranking vol or time fattens the price curve: the value of
 * optionality is the value of uncertainty.
 */
export default function BlackScholesGreeks() {
  const [vol, setVol] = useState(0.25);
  const [t, setT] = useState(0.5);
  const [show, setShow] = useState<"delta" | "gamma">("delta");

  const data = useMemo(() => {
    const pts = [];
    for (let S = 50; S <= 150; S += 1) {
      const d1 = (Math.log(S / K) + (0.5 * vol * vol) * t) / (vol * Math.sqrt(t));
      const d2 = d1 - vol * Math.sqrt(t);
      const price = S * normalCdf(d1) - K * normalCdf(d2);
      const delta = normalCdf(d1);
      const gamma = normalPdf(d1) / (S * vol * Math.sqrt(t));
      pts.push({ S, price: +price.toFixed(2), delta: +delta.toFixed(3), gamma: +(gamma * 100).toFixed(3) });
    }
    return pts;
  }, [vol, t]);

  return (
    <VizFrame
      caption={
        <>
          Schwarz = Call-Preis (Strike {K}). <span className="text-emerald-300">Delta</span> = N(d₁) ist die
          Steigung = Hedge-Ratio; <span className="text-amber-300">Gamma</span> (×100) ist die Krümmung und
          ist am Geld maximal — was Optionsverkäufer short sind. Mehr Vol/Zeit ⇒ wertvollere Optionalität.
        </>
      }
    >
      <div className="mb-3 flex flex-wrap items-end gap-6">
        <Slider label="Volatilität σ" value={vol} min={0.05} max={0.8} step={0.01} onChange={setVol} fmt={(v) => `${(v * 100).toFixed(0)}%`} />
        <Slider label="Restlaufzeit T (J)" value={t} min={0.05} max={2} step={0.05} onChange={setT} fmt={(v) => v.toFixed(2)} accent="accent-amber-500" />
        <div className="flex gap-1 text-xs">
          {(["delta", "gamma"] as const).map((g) => (
            <button key={g} onClick={() => setShow(g)} className={`rounded border px-2 py-1 capitalize ${show === g ? "border-blue-500 bg-blue-500/10 text-blue-200" : "border-zinc-700 text-zinc-400"}`}>{g}</button>
          ))}
        </div>
      </div>
      <ResponsiveContainer width="100%" height={240}>
        <LineChart data={data}>
          <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
          <XAxis dataKey="S" tick={AXIS} label={{ value: "Spot S", fill: "#a1a1aa", fontSize: 10, dy: 12 }} />
          <YAxis yAxisId="l" tick={AXIS} width={40} />
          <YAxis yAxisId="r" orientation="right" tick={AXIS} width={40} />
          <Tooltip contentStyle={TOOLTIP} />
          <ReferenceLine yAxisId="l" x={K} stroke="#52525b" strokeDasharray="4 3" label={{ value: "Strike", fill: "#a1a1aa", fontSize: 10 }} />
          <Line yAxisId="l" dataKey="price" stroke="#e4e4e7" dot={false} strokeWidth={2} isAnimationActive={false} />
          <Line yAxisId="r" dataKey={show} stroke={show === "delta" ? "#22c55e" : "#eab308"} dot={false} strokeWidth={2} isAnimationActive={false} />
        </LineChart>
      </ResponsiveContainer>
    </VizFrame>
  );
}
