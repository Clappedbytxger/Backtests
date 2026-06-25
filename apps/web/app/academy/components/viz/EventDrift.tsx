"use client";

import { useMemo, useState } from "react";
import { Bar, BarChart, CartesianGrid, Cell, ReferenceArea, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { AXIS, GRID, gauss, rng, Slider, TOOLTIP, VizFrame } from "./controls";

const OFFSETS = Array.from({ length: 21 }, (_, i) => i - 10); // −10 … +10
const WINDOW = new Set([-1, 0]); // the true pre-event drift window

/** True average return (bps) at an offset: a real bump only in the pre-event window. */
const trueEffect = (o: number) => (WINDOW.has(o) ? 8 : 0);

/**
 * Event-driven drift. Returns are averaged across N events, aligned to the event day (offset
 * 0). The real effect lives in a narrow PRE-event window (−1, 0) — the rest is noise. With
 * few events the noise makes random offsets look real; only with enough events does the true
 * window stand out (Module 1 power). This is why the right null is "random timing", not 0.
 */
export default function EventDrift() {
  const [nEvents, setNEvents] = useState(40);

  const { bars, windowMean, se } = useMemo(() => {
    const r = rng(2024);
    const noiseSd = 25; // per-event daily noise (bps)
    const bars = OFFSETS.map((o) => {
      let sum = 0;
      for (let e = 0; e < nEvents; e++) sum += trueEffect(o) + noiseSd * gauss(r);
      return { offset: o, avg: +(sum / nEvents).toFixed(2), inWindow: WINDOW.has(o) };
    });
    const se = noiseSd / Math.sqrt(nEvents);
    const windowMean = bars.filter((b) => b.inWindow).reduce((s, b) => s + b.avg, 0) / WINDOW.size;
    return { bars, windowMean, se };
  }, [nEvents]);

  return (
    <VizFrame
      caption={
        <>
          Durchschnittlicher Return je Offset um den Event-Tag (0), über {nEvents} Events. Der echte Effekt
          (+8 bps) sitzt nur im <span className="text-amber-400">Fenster −1/0</span>; der Rest ist Rauschen.
          Standardfehler je Balken ≈ <b>{se.toFixed(1)} bps</b> — mit wenigen Events ragen zufällige Offsets
          heraus, erst genug Events lassen das wahre Fenster hervortreten (Modul 1). Darum ist die richtige
          Null „Zufalls-Timing", nicht 0.
        </>
      }
    >
      <div className="mb-3 flex flex-wrap gap-6">
        <Slider label="Anzahl Events" value={nEvents} min={10} max={400} step={10} onChange={setNEvents} fmt={(v) => String(Math.round(v))} width="w-56" />
      </div>
      <ResponsiveContainer width="100%" height={240}>
        <BarChart data={bars}>
          <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
          <ReferenceArea x1={-1.5} x2={0.5} fill="#f59e0b" fillOpacity={0.08} />
          <XAxis dataKey="offset" tick={AXIS} label={{ value: "Tage relativ zum Event", fill: "#a1a1aa", fontSize: 10, dy: 12 }} />
          <YAxis tick={AXIS} width={42} label={{ value: "Ø bps", angle: -90, position: "insideLeft", fill: "#a1a1aa", fontSize: 10 }} />
          <Tooltip contentStyle={TOOLTIP} formatter={(v) => `${Number(v).toFixed(1)} bps`} />
          <Bar dataKey="avg" isAnimationActive={false}>
            {bars.map((b, i) => (
              <Cell key={i} fill={b.inWindow ? "#f59e0b" : "#3f3f46"} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </VizFrame>
  );
}
