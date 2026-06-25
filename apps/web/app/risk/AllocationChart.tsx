"use client";

import {
  Bar,
  BarChart,
  Cell,
  CartesianGrid,
  LabelList,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { RiskAllocation } from "@/lib/api";

/**
 * Capital allocation vs. the actual risk it generates. Two bars per sleeve:
 * the assigned weight (capital %) and its marginal contribution to portfolio risk.
 * A sleeve whose RED risk bar towers over its CYAN allocation bar is silently
 * driving the book — the core "where is my risk really" read.
 */
export default function AllocationChart({ alloc }: { alloc: RiskAllocation }) {
  const short = (l: string) => l.slice(0, 4);
  const rows = Object.keys(alloc.weights)
    .map((k) => ({
      name: short(k),
      full: k,
      Allokation: +(alloc.weights[k] * 100).toFixed(2),
      Risiko: +((alloc.risk_contribution[k] ?? 0) * 100).toFixed(2),
    }))
    .sort((a, b) => b.Allokation - a.Allokation);

  const height = Math.max(220, rows.length * 38 + 40);

  return (
    <div style={{ width: "100%", height }}>
      <ResponsiveContainer>
        <BarChart data={rows} layout="vertical" margin={{ top: 4, right: 28, left: 4, bottom: 4 }} barGap={2}>
          <CartesianGrid strokeDasharray="3 3" stroke="#27272a" horizontal={false} />
          <XAxis
            type="number"
            tick={{ fill: "#71717a", fontSize: 10 }}
            tickFormatter={(v) => `${v}%`}
            stroke="#3f3f46"
          />
          <YAxis
            type="category"
            dataKey="name"
            width={42}
            tick={{ fill: "#a1a1aa", fontSize: 10, fontFamily: "monospace" }}
            stroke="#3f3f46"
          />
          <Tooltip
            cursor={{ fill: "rgba(255,255,255,0.04)" }}
            contentStyle={{
              background: "#09090b",
              border: "1px solid #3f3f46",
              borderRadius: 8,
              fontSize: 12,
            }}
            labelFormatter={(_l, p) => (p && p[0] ? (p[0].payload as { full: string }).full : "")}
            formatter={(v: unknown, n: unknown) => [`${v}%`, String(n)]}
          />
          <Legend wrapperStyle={{ fontSize: 11 }} />
          <Bar dataKey="Allokation" fill="#22d3ee" radius={[0, 3, 3, 0]} maxBarSize={14}>
            <LabelList dataKey="Allokation" position="right" fill="#71717a" fontSize={9} formatter={(v: unknown) => `${v}%`} />
          </Bar>
          <Bar dataKey="Risiko" radius={[0, 3, 3, 0]} maxBarSize={14}>
            {rows.map((r) => (
              // risk bar burns red when it exceeds the capital allocation (over-contributor)
              <Cell key={r.name} fill={r.Risiko > r.Allokation + 1 ? "#ef4444" : "#f59e0b"} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
