"use client";

import { useMemo, useState } from "react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

/** Box-Muller: one standard-normal draw from two uniforms. */
function gauss(rand: () => number) {
  const u1 = Math.max(rand(), 1e-9);
  const u2 = rand();
  return Math.sqrt(-2 * Math.log(u1)) * Math.cos(2 * Math.PI * u2);
}

/** Deterministic PRNG (mulberry32) so a given seed reproduces a path. */
function rng(seed: number) {
  let a = seed;
  return () => {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const COLORS = ["#3b82f6", "#22c55e", "#eab308", "#ef4444", "#a855f7"];
const N = 250; // ~1 trading year of steps
const PATHS = 5;

/**
 * Geometric Brownian motion: price_t = price_{t-1} * exp(mu/N + sigma/sqrt(N) * Z).
 * Re-roll the seed and watch 5 random paths fan out from the same start — the core
 * intuition that a "trend" can be pure noise (the 0040 "Intraday-Brutto 0"-Frage).
 */
export default function RandomWalk() {
  const [seed, setSeed] = useState(7);
  const [drift, setDrift] = useState(0.05); // annual mu
  const [vol, setVol] = useState(0.2); // annual sigma

  const data = useMemo(() => {
    const paths: number[][] = [];
    for (let p = 0; p < PATHS; p++) {
      const r = rng(seed * 1000 + p * 17 + 1);
      const series = [100];
      for (let i = 1; i <= N; i++) {
        const z = gauss(r);
        const prev = series[i - 1];
        series.push(prev * Math.exp(drift / N + (vol / Math.sqrt(N)) * z));
      }
      paths.push(series);
    }
    return Array.from({ length: N + 1 }, (_, i) => {
      const row: Record<string, number> = { t: i };
      paths.forEach((s, p) => (row[`p${p}`] = +s[i].toFixed(2)));
      return row;
    });
  }, [seed, drift, vol]);

  return (
    <div className="rounded-lg border border-zinc-800 bg-zinc-900/40 p-4">
      <div className="mb-3 flex flex-wrap items-end gap-6">
        <Slider label="μ (Drift p.a.)" value={drift} min={-0.3} max={0.3} step={0.01} onChange={setDrift} fmt={(v) => `${(v * 100).toFixed(0)}%`} />
        <Slider label="σ (Vol p.a.)" value={vol} min={0.05} max={0.6} step={0.01} onChange={setVol} fmt={(v) => `${(v * 100).toFixed(0)}%`} />
        <button
          onClick={() => setSeed((s) => s + 1)}
          className="rounded-md border border-zinc-700 bg-zinc-800 px-3 py-1.5 text-xs text-zinc-200 hover:border-zinc-500"
        >
          ↻ Neu würfeln
        </button>
      </div>
      <ResponsiveContainer width="100%" height={260}>
        <LineChart data={data}>
          <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
          <XAxis dataKey="t" tick={{ fill: "#a1a1aa", fontSize: 11 }} />
          <YAxis tick={{ fill: "#a1a1aa", fontSize: 11 }} width={42} domain={["auto", "auto"]} />
          <Tooltip contentStyle={{ background: "#18181b", border: "1px solid #3f3f46" }} />
          {Array.from({ length: PATHS }, (_, p) => (
            <Line
              key={p}
              dataKey={`p${p}`}
              stroke={COLORS[p]}
              dot={false}
              strokeWidth={1.5}
              isAnimationActive={false}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
      <p className="mt-2 text-xs text-zinc-500">
        Alle 5 Pfade haben <em>dieselbe</em> Drift &amp; Vol — die Unterschiede sind reiner Zufall.
        Manche „trenden“ überzeugend nach oben, obwohl kein Pfad mehr Information hat als die anderen.
        Genau deshalb braucht ein echter Edge einen Signifikanztest.
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
  fmt,
}: {
  label: string;
  value: number;
  min: number;
  max: number;
  step: number;
  onChange: (v: number) => void;
  fmt: (v: number) => string;
}) {
  return (
    <label className="flex flex-col text-xs text-zinc-400">
      <span className="mb-1">
        {label}: <span className="font-mono text-zinc-200">{fmt(value)}</span>
      </span>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(parseFloat(e.target.value))}
        className="w-40 accent-blue-500"
      />
    </label>
  );
}
