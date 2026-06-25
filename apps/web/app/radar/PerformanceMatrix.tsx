"use client";

import type { RegimeCode, RegimePerformanceResponse } from "@/lib/api";

const ORDER: RegimeCode[] = ["high_vol_trend", "low_vol_trend", "high_vol_range", "low_vol_range"];

// which regimes each toy strategy CLAIMS to target (the "Soll")
const TARGET: Record<string, RegimeCode[]> = {
  buy_hold: [],
  long_trend: ["high_vol_trend", "low_vol_trend"],
  long_quiet: ["low_vol_range"],
};

const pct = (x: number) => `${x >= 0 ? "+" : ""}${(x * 100).toFixed(1)}%`;

/** Heat colour for a return cell: green for gains, red for losses, scaled. */
function heat(v: number): string {
  const a = Math.min(Math.abs(v) / 0.6, 1); // saturate around ±60%
  return v >= 0
    ? `rgba(34,197,94,${0.12 + a * 0.5})`
    : `rgba(239,68,68,${0.12 + a * 0.5})`;
}

/**
 * Regime-performance matrix — proves in which regimes the chosen rule actually
 * earned (Ist), and marks the regimes it was supposed to work in (Soll).
 */
export default function PerformanceMatrix({ data }: { data: RegimePerformanceResponse }) {
  const target = new Set(TARGET[data.strategy] ?? []);
  const by = data.by_regime;
  const maxRet = Math.max(...ORDER.map((c) => Math.abs(by[c]?.total_return ?? 0)), 0.01);

  return (
    <div>
      {/* horizontal regime return bars */}
      <div className="space-y-2.5">
        {ORDER.map((c) => {
          const e = by[c];
          if (!e) return null;
          const w = (Math.abs(e.total_return) / maxRet) * 100;
          const soll = target.has(c);
          return (
            <div key={c} className="flex items-center gap-3">
              <div className="flex w-44 shrink-0 items-center gap-2">
                <span className="h-3 w-3 rounded-sm" style={{ background: e.color }} />
                <span className="text-xs text-zinc-300">{e.label}</span>
                {soll && (
                  <span className="rounded border border-amber-500/50 px-1 text-[9px] uppercase tracking-wide text-amber-300">
                    Soll
                  </span>
                )}
              </div>
              <div className="relative h-6 flex-1 rounded bg-zinc-900">
                <div
                  className="absolute inset-y-0 left-0 rounded"
                  style={{
                    width: `${w}%`,
                    background: e.total_return >= 0 ? "#22c55e" : "#ef4444",
                    opacity: 0.55,
                  }}
                />
                <span className="absolute inset-y-0 left-2 flex items-center font-mono text-[11px] text-zinc-100">
                  {pct(e.total_return)}
                </span>
                <span className="absolute inset-y-0 right-2 flex items-center font-mono text-[10px] text-zinc-500">
                  Sharpe {e.sharpe.toFixed(2)} · {(e.pct_of_time * 100).toFixed(0)}% Zeit
                </span>
              </div>
            </div>
          );
        })}
      </div>

      {/* detail heat-table */}
      <div className="mt-5 overflow-hidden rounded-lg border border-zinc-800">
        <table className="w-full text-right text-xs">
          <thead className="bg-zinc-900/70 text-[10px] uppercase tracking-wide text-zinc-500">
            <tr>
              <th className="px-3 py-2 text-left">Regime</th>
              <th className="px-3 py-2">Return</th>
              <th className="px-3 py-2">Sharpe</th>
              <th className="px-3 py-2">Trefferquote</th>
              <th className="px-3 py-2">MaxDD</th>
              <th className="px-3 py-2">Zeitanteil</th>
            </tr>
          </thead>
          <tbody className="font-mono text-zinc-200">
            {ORDER.map((c) => {
              const e = by[c];
              if (!e) return null;
              return (
                <tr key={c} className="border-t border-zinc-800/70">
                  <td className="px-3 py-2 text-left font-sans">
                    <span className="flex items-center gap-2">
                      <span className="h-2.5 w-2.5 rounded-sm" style={{ background: e.color }} />
                      {e.label}
                      {target.has(c) && <span className="text-[9px] text-amber-400">●</span>}
                    </span>
                  </td>
                  <td className="px-3 py-2" style={{ background: heat(e.total_return) }}>
                    {pct(e.total_return)}
                  </td>
                  <td className="px-3 py-2">{e.sharpe.toFixed(2)}</td>
                  <td className="px-3 py-2">{(e.win_rate * 100).toFixed(0)}%</td>
                  <td className="px-3 py-2 text-red-300">{pct(e.max_drawdown)}</td>
                  <td className="px-3 py-2 text-zinc-400">{(e.pct_of_time * 100).toFixed(0)}%</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      {target.size > 0 && (
        <p className="mt-3 text-[11px] text-zinc-500">
          <span className="text-amber-400">● Soll</span> = Regimes, in denen diese Regel laut
          Hypothese funktionieren soll. Vergleiche Ist-Return/Sharpe dort gegen die übrigen Regimes,
          um den Agenten-Tipp zu prüfen.
        </p>
      )}
    </div>
  );
}
