"use client";

import { useMemo, useState } from "react";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { AXIS, GRID, gauss, rng, Slider, TOOLTIP, VizFrame } from "./controls";

const DAYS = 252;
const SHOWN = 40; // plotted paths
const TOTAL = 400; // paths used for the pass-probability estimate

/** One equity path; returns its max trailing peak-to-trough drawdown (fraction). */
function simulate(r: () => number, mu: number, sigma: number, equity: number[]): number {
  let e = 1;
  let peak = 1;
  let maxDD = 0;
  equity.length = 0;
  equity.push(100);
  for (let d = 0; d < DAYS; d++) {
    // fat-tailed daily return: gaussian scaled by an occasional shock
    const shock = r() < 0.04 ? 2.5 : 1;
    const ret = mu / DAYS + (sigma / Math.sqrt(DAYS)) * gauss(r) * shock;
    e *= 1 + ret;
    peak = Math.max(peak, e);
    maxDD = Math.max(maxDD, (peak - e) / peak);
    equity.push(+(e * 100).toFixed(2));
  }
  return maxDD;
}

/**
 * Prop-account survival as Monte-Carlo. Many equity paths are drawn from the same edge
 * (μ, σ) with fat-tailed daily shocks. A path FAILS if its trailing peak-to-trough drawdown
 * ever breaches the limit. The pass-probability — not the average return — is what decides a
 * prop challenge: a positive-EV edge with a 40 % ruin rate is useless (0070 funded-account).
 */
export default function DrawdownPaths() {
  const [mu, setMu] = useState(0.2);
  const [sigma, setSigma] = useState(0.12);
  const [limit, setLimit] = useState(0.15);

  const { data, passPct } = useMemo(() => {
    // pass probability over many paths
    let pass = 0;
    const r1 = rng(1234);
    const buf: number[] = [];
    for (let i = 0; i < TOTAL; i++) if (simulate(r1, mu, sigma, buf) <= limit) pass++;
    const passPct = (100 * pass) / TOTAL;

    // a sample of paths to plot, each tagged passed/failed
    const r2 = rng(77);
    const paths: { dd: number; eq: number[] }[] = [];
    for (let i = 0; i < SHOWN; i++) {
      const eq: number[] = [];
      const dd = simulate(r2, mu, sigma, eq);
      paths.push({ dd, eq: [...eq] });
    }
    const data = Array.from({ length: DAYS + 1 }, (_, d) => {
      const row: Record<string, number> = { d };
      paths.forEach((p, i) => (row[`p${i}`] = p.eq[d]));
      return row;
    });
    return { data, passPct, paths };
  }, [mu, sigma, limit]);

  // recompute fail flags for colouring (cheap; mirrors the plotted paths)
  const failFlags = useMemo(() => {
    const r2 = rng(77);
    const buf: number[] = [];
    return Array.from({ length: SHOWN }, () => simulate(r2, mu, sigma, buf) > limit);
  }, [mu, sigma, limit]);

  return (
    <VizFrame
      caption={
        <>
          {SHOWN} von {TOTAL} simulierten Pfaden (μ {(mu * 100).toFixed(0)} %, σ {(sigma * 100).toFixed(0)} % p.a.,
          Fat-Tail-Schocks). <span className="text-red-400">Rot</span> = Trailing-Drawdown reißt das{" "}
          {(limit * 100).toFixed(0)} %-Limit, <span className="text-emerald-400">Grün</span> = besteht.
          Pass-Wahrscheinlichkeit = <b className={passPct >= 75 ? "text-emerald-400" : "text-amber-400"}>{passPct.toFixed(0)} %</b>.
          Nicht der Mittelwert entscheidet die Challenge, sondern dieser Anteil.
        </>
      }
    >
      <div className="mb-3 flex flex-wrap gap-6">
        <Slider label="Rendite μ p.a." value={mu} min={-0.1} max={0.5} step={0.01} onChange={setMu} fmt={(v) => `${(v * 100).toFixed(0)}%`} accent="accent-emerald-500" />
        <Slider label="Volatilität σ p.a." value={sigma} min={0.05} max={0.5} step={0.01} onChange={setSigma} fmt={(v) => `${(v * 100).toFixed(0)}%`} />
        <Slider label="DD-Limit" value={limit} min={0.04} max={0.25} step={0.01} onChange={setLimit} fmt={(v) => `${(v * 100).toFixed(0)}%`} accent="accent-red-500" />
      </div>
      <ResponsiveContainer width="100%" height={260}>
        <LineChart data={data}>
          <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
          <XAxis dataKey="d" tick={AXIS} label={{ value: "Handelstage", fill: "#a1a1aa", fontSize: 10, dy: 12 }} />
          <YAxis tick={AXIS} width={42} domain={["auto", "auto"]} />
          <Tooltip contentStyle={TOOLTIP} />
          {Array.from({ length: SHOWN }, (_, i) => (
            <Line
              key={i}
              dataKey={`p${i}`}
              stroke={failFlags[i] ? "#ef4444" : "#22c55e"}
              strokeOpacity={failFlags[i] ? 0.45 : 0.4}
              dot={false}
              strokeWidth={1}
              isAnimationActive={false}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </VizFrame>
  );
}
