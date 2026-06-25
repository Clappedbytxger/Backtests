"use client";

import type { PairHeatmapResponse } from "@/lib/api";

/**
 * Cointegration matrix: cell colour = strength (1 − ADF p-value). Bright cyan
 * means strongly cointegrated (p→0), dark means independent (p→1). Clicking a
 * cell selects that pair. Cells with p < 0.05 get a ring (the tradable cluster).
 */
export default function CointHeatmap({
  data,
  onSelect,
}: {
  data: PairHeatmapResponse;
  onSelect?: (a: string, b: string) => void;
}) {
  const { tickers, strength, pvalue } = data;
  const n = tickers.length;

  // cyan-scale: strength 0 → near-black, 1 → bright cyan
  const cell = (s: number | null) => {
    if (s == null) return "#18181b";
    const a = Math.max(0, Math.min(s, 1));
    // emphasize the high end (cointegration lives near p<0.05 ⇒ strength>0.95)
    const e = Math.pow(a, 6);
    return `rgba(34, 211, 238, ${0.05 + e * 0.95})`;
  };

  return (
    <div className="overflow-x-auto">
      <table className="border-separate" style={{ borderSpacing: 2 }}>
        <thead>
          <tr>
            <th className="sticky left-0 bg-zinc-950" />
            {tickers.map((t) => (
              <th key={t} className="px-1 pb-1 text-[9px] font-normal text-zinc-500">
                <span className="inline-block rotate-0">{t}</span>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {tickers.map((rowT, i) => (
            <tr key={rowT}>
              <td className="sticky left-0 z-10 bg-zinc-950 pr-2 text-right text-[10px] text-zinc-400">
                {rowT}
              </td>
              {tickers.map((colT, j) => {
                const s = strength[i]?.[j] ?? null;
                const p = pvalue[i]?.[j] ?? null;
                const coint = p != null && p < 0.05 && i !== j;
                return (
                  <td key={colT} className="p-0">
                    <button
                      disabled={i === j}
                      onClick={() => onSelect?.(rowT, colT)}
                      title={
                        i === j ? rowT : `${rowT} / ${colT}\nADF p = ${p ?? "n/a"}\nstrength = ${s ?? "n/a"}`
                      }
                      className="h-7 w-7 rounded-sm transition hover:outline hover:outline-1 hover:outline-zinc-300 disabled:cursor-default"
                      style={{
                        background: i === j ? "#0a0a0a" : cell(s),
                        outline: coint ? "1.5px solid #22d3ee" : "none",
                      }}
                    >
                      {coint && (
                        <span className="text-[8px] font-semibold text-cyan-100">
                          {p != null ? (p * 100).toFixed(0) : ""}
                        </span>
                      )}
                    </button>
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
      <div className="mt-3 flex items-center gap-3 text-[10px] text-zinc-500">
        <span>schwach</span>
        <div className="h-2.5 w-40 rounded-full"
          style={{ background: "linear-gradient(90deg, rgba(34,211,238,0.05), rgba(34,211,238,1))" }} />
        <span>stark kointegriert</span>
        <span className="ml-3 rounded px-1 text-cyan-200 outline outline-1 outline-cyan-400">
          umrandet = p&lt;0.05 (handelbar) · Zahl = p-Value in %
        </span>
      </div>
    </div>
  );
}
