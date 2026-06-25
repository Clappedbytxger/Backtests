"use client";

/** Shared controls + math helpers for the Academy visualisations. */

export function Slider({
  label,
  value,
  min,
  max,
  step,
  onChange,
  fmt = (v) => v.toFixed(1),
  accent = "accent-blue-500",
  width = "w-44",
}: {
  label: string;
  value: number;
  min: number;
  max: number;
  step: number;
  onChange: (v: number) => void;
  fmt?: (v: number) => string;
  accent?: string;
  width?: string;
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
        className={`${width} ${accent}`}
      />
    </label>
  );
}

/** Deterministic PRNG (mulberry32): same seed ⇒ same sequence. */
export function rng(seed: number) {
  let a = seed;
  return () => {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/** One standard-normal draw (Box–Muller). */
export function gauss(rand: () => number) {
  const u1 = Math.max(rand(), 1e-9);
  return Math.sqrt(-2 * Math.log(u1)) * Math.cos(2 * Math.PI * rand());
}

/** Standard normal PDF / CDF (Abramowitz–Stegun approximation for the CDF). */
export function normalPdf(x: number, mu = 0, sigma = 1) {
  const z = (x - mu) / sigma;
  return Math.exp(-0.5 * z * z) / (sigma * Math.sqrt(2 * Math.PI));
}
export function normalCdf(x: number) {
  const t = 1 / (1 + 0.2316419 * Math.abs(x));
  const d = 0.3989423 * Math.exp(-(x * x) / 2);
  const p =
    d * t * (0.3193815 + t * (-0.3565638 + t * (1.781478 + t * (-1.821256 + t * 1.330274))));
  return x > 0 ? 1 - p : p;
}

export const TOOLTIP = { background: "#18181b", border: "1px solid #3f3f46" } as const;
export const GRID = "#27272a";
export const AXIS = { fill: "#a1a1aa", fontSize: 11 } as const;

export function VizFrame({ children, caption }: { children: React.ReactNode; caption: React.ReactNode }) {
  return (
    <div className="rounded-lg border border-zinc-800 bg-zinc-900/40 p-4">
      {children}
      <p className="mt-2 text-xs text-zinc-500">{caption}</p>
    </div>
  );
}
