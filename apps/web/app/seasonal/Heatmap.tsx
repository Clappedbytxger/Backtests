"use client";

import { useMemo } from "react";
import type { SeasonalHeatmapResponse } from "@/lib/api";

/** Diverging green/red cell background — opacity scales with |value| / cap. */
function cellStyle(v: number | null, cap: number): React.CSSProperties {
  if (v == null) return { background: "transparent" };
  const a = Math.min(1, Math.abs(v) / cap) * 0.85 + 0.05;
  // emerald-500 / red-500 in rgb
  return v >= 0
    ? { background: `rgba(16,185,129,${a})` }
    : { background: `rgba(239,68,68,${a})` };
}

const fmt = (v: number | null) => (v == null ? "" : `${v >= 0 ? "+" : ""}${v.toFixed(1)}`);

/**
 * Month-by-year performance heatmap (Seasonax-style). Rows = years (newest on
 * top), columns = Jan..Dec + a compounded yearly total. The colour cap is the
 * 95th percentile of |monthly returns| so a single outlier month doesn't wash
 * out the scale.
 */
export default function Heatmap({ data }: { data: SeasonalHeatmapResponse }) {
  const { years, months, matrix, monthly_avg, yearly_total } = data;

  const cap = useMemo(() => {
    const vals = matrix.flat().filter((v): v is number => v != null).map(Math.abs).sort((a, b) => a - b);
    if (!vals.length) return 1;
    const p95 = vals[Math.floor(vals.length * 0.95)] ?? vals[vals.length - 1];
    return Math.max(p95, 1);
  }, [matrix]);

  // Newest year first for a natural top-down read.
  const order = useMemo(() => years.map((_, i) => i).reverse(), [years]);

  return (
    <div className="overflow-x-auto">
      <table className="w-full border-separate border-spacing-0.5 text-[11px]">
        <thead>
          <tr className="text-zinc-500">
            <th className="sticky left-0 z-10 bg-zinc-950 px-2 py-1 text-left font-medium">Jahr</th>
            {months.map((m) => (
              <th key={m} className="px-1 py-1 text-center font-medium">{m}</th>
            ))}
            <th className="px-2 py-1 text-center font-semibold text-zinc-400">Jahr Σ</th>
          </tr>
        </thead>
        <tbody>
          {order.map((ri) => (
            <tr key={years[ri]}>
              <td className="sticky left-0 z-10 bg-zinc-950 px-2 py-1 font-mono text-zinc-400">
                {years[ri]}
              </td>
              {matrix[ri].map((v, ci) => (
                <td
                  key={ci}
                  className="px-1 py-1 text-center font-mono tabular-nums text-zinc-100"
                  style={cellStyle(v, cap)}
                  title={v == null ? "–" : `${months[ci]} ${years[ri]}: ${fmt(v)}%`}
                >
                  {fmt(v)}
                </td>
              ))}
              <td
                className="px-2 py-1 text-center font-mono font-semibold tabular-nums text-zinc-50"
                style={cellStyle(yearly_total[ri], cap * 2.5)}
              >
                {fmt(yearly_total[ri])}
              </td>
            </tr>
          ))}
          {/* Average row */}
          <tr className="border-t border-zinc-700">
            <td className="sticky left-0 z-10 bg-zinc-950 px-2 py-1 font-semibold text-zinc-300">Ø</td>
            {monthly_avg.map((v, ci) => (
              <td
                key={ci}
                className="px-1 py-1 text-center font-mono font-semibold tabular-nums text-zinc-50"
                style={cellStyle(v, cap)}
              >
                {fmt(v)}
              </td>
            ))}
            <td className="bg-zinc-900 px-2 py-1" />
          </tr>
        </tbody>
      </table>
      <p className="mt-2 text-[11px] text-zinc-500">
        Monatsrenditen in %. Grün = positiv, Rot = negativ (Intensität skaliert auf das 95.
        Perzentil). Die <span className="text-zinc-300">Ø-Zeile</span> zeigt das saisonale Mittel je
        Monat, die <span className="text-zinc-300">Jahr-Σ-Spalte</span> die aufgezinste Jahresrendite.
      </p>
    </div>
  );
}
