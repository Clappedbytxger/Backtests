"use client";

import { useMemo, useState } from "react";
import { CartesianGrid, ComposedChart, Line, ResponsiveContainer, Scatter, Tooltip, XAxis, YAxis, ZAxis } from "recharts";
import { AXIS, GRID, Slider, TOOLTIP, VizFrame } from "./controls";

// Convex loss f(x) = x^2 with gradient f'(x) = 2x — the minimal model of training.
const f = (x: number) => x * x;
const grad = (x: number) => 2 * x;
const START = -4.5;

/**
 * Gradient descent on a parabola: x ← x − η·f'(x). Step through it and watch the iterate
 * roll downhill. Push the learning rate η past 1 and the steps OVERSHOOT and diverge —
 * the single most important intuition for why every ML optimiser has a learning rate.
 */
export default function GradientDescent() {
  const [lr, setLr] = useState(0.1);
  const [traj, setTraj] = useState<number[]>([START]);

  const curve = useMemo(() => {
    const pts = [];
    for (let x = -5; x <= 5; x += 0.1) pts.push({ x: +x.toFixed(2), y: +f(x).toFixed(3) });
    return pts;
  }, []);

  const step = () => {
    setTraj((t) => {
      const x = t[t.length - 1];
      const nx = x - lr * grad(x);
      return [...t, Math.max(-6, Math.min(6, nx))];
    });
  };
  const run = () => {
    let t = [...traj];
    for (let i = 0; i < 12; i++) {
      const x = t[t.length - 1];
      t = [...t, Math.max(-6, Math.min(6, x - lr * grad(x)))];
    }
    setTraj(t);
  };
  const reset = () => setTraj([START]);

  const points = traj.map((x) => ({ x: +x.toFixed(3), y: +f(x).toFixed(3) }));
  const last = traj[traj.length - 1];
  const diverging = Math.abs(last) > Math.abs(traj[0]) + 0.01;

  return (
    <VizFrame
      caption={
        <>
          Aktuell x = {last.toFixed(2)}, Verlust = {f(last).toFixed(2)} nach {traj.length - 1} Schritten.{" "}
          {diverging ? (
            <b className="text-red-400">η zu groß — die Schritte explodieren statt zu konvergieren.</b>
          ) : (
            <span>Bei η &lt; 1 rollt der Punkt sauber ins Minimum bei 0.</span>
          )}{" "}
          Genau dieser Trade-off steckt in jedem LightGBM-/NN-Training.
        </>
      }
    >
      <div className="mb-3 flex flex-wrap items-end gap-4">
        <Slider label="Lernrate η" value={lr} min={0.02} max={1.15} step={0.01} onChange={setLr} fmt={(v) => v.toFixed(2)} />
        <button onClick={step} className="rounded-md border border-zinc-700 bg-zinc-800 px-3 py-1.5 text-xs text-zinc-200 hover:border-zinc-500">1 Schritt</button>
        <button onClick={run} className="rounded-md border border-blue-700 bg-blue-900/40 px-3 py-1.5 text-xs text-blue-200 hover:border-blue-500">12 Schritte</button>
        <button onClick={reset} className="rounded-md border border-zinc-700 bg-zinc-800 px-3 py-1.5 text-xs text-zinc-400 hover:border-zinc-500">Reset</button>
      </div>
      <ResponsiveContainer width="100%" height={240}>
        <ComposedChart data={curve}>
          <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
          <XAxis dataKey="x" type="number" domain={[-5, 5]} tick={AXIS} />
          <YAxis tick={AXIS} width={36} domain={[0, 26]} />
          <ZAxis range={[60, 60]} />
          <Tooltip contentStyle={TOOLTIP} />
          <Line dataKey="y" stroke="#3f3f46" dot={false} strokeWidth={2} isAnimationActive={false} />
          <Scatter data={points} line={{ stroke: "#22c55e", strokeWidth: 1 }} fill="#22c55e" isAnimationActive={false} />
        </ComposedChart>
      </ResponsiveContainer>
    </VizFrame>
  );
}
