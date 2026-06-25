"use client";

import {
  Area,
  AreaChart,
  CartesianGrid,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { RiskCorrelationSeries } from "@/lib/api";

/** Rolling correlation of one pair over time — "is the diversification still there?". */
export default function RollingCorr({ data }: { data: RiskCorrelationSeries }) {
  const rows = data.series.map((p) => ({ t: p.t, corr: p.corr }));
  return (
    <div className="rounded-lg border border-zinc-800 bg-zinc-900/40 p-3">
      <div className="mb-1 flex items-baseline justify-between">
        <div className="text-xs font-medium text-zinc-300">
          Rolling-Korrelation · {data.a.slice(0, 4)} × {data.b.slice(0, 4)}
          <span className="ml-2 text-[10px] text-zinc-500">{data.rolling_window}-Tage-Fenster</span>
        </div>
        <div className="font-mono text-xs text-zinc-400">
          ρ gesamt ={" "}
          <span className={(data.full_correlation ?? 0) > 0.6 ? "text-red-300" : "text-zinc-200"}>
            {data.full_correlation == null ? "n/a" : data.full_correlation.toFixed(3)}
          </span>
        </div>
      </div>
      <div style={{ width: "100%", height: 160 }}>
        <ResponsiveContainer>
          <AreaChart data={rows} margin={{ top: 6, right: 12, left: -18, bottom: 0 }}>
            <defs>
              <linearGradient id="corrFill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#22d3ee" stopOpacity={0.35} />
                <stop offset="100%" stopColor="#22d3ee" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
            <XAxis dataKey="t" tick={{ fill: "#52525b", fontSize: 9 }} minTickGap={48} stroke="#3f3f46" />
            <YAxis domain={[-1, 1]} ticks={[-1, -0.5, 0, 0.5, 1]} tick={{ fill: "#71717a", fontSize: 9 }} stroke="#3f3f46" />
            <ReferenceLine y={0} stroke="#52525b" />
            <ReferenceLine y={0.6} stroke="#7f1d1d" strokeDasharray="4 4" />
            <Tooltip
              contentStyle={{ background: "#09090b", border: "1px solid #3f3f46", borderRadius: 8, fontSize: 12 }}
              formatter={(v: unknown) => [Number(v).toFixed(3), "ρ"]}
            />
            <Area type="monotone" dataKey="corr" stroke="#22d3ee" strokeWidth={1.5} fill="url(#corrFill)" />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
