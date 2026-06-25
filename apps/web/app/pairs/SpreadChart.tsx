"use client";

import { useMemo } from "react";
import {
  CartesianGrid,
  ComposedChart,
  Line,
  ReferenceArea,
  ReferenceLine,
  ResponsiveContainer,
  Scatter,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { PairDetailResponse } from "@/lib/api";

/**
 * The core stat-arb visualization: the spread's rolling Z-Score over time with
 * the ±2 / 0 mean-reversion bands and entry/exit signal dots painted on the line.
 * Long entries = neon green, short entries = alarm red, exits = cyan.
 */
export default function SpreadChart({ data }: { data: PairDetailResponse }) {
  const rows = useMemo(() => {
    const base = data.series.map((p, i) => ({
      i,
      t: p.t,
      z: p.z,
      spread: p.spread,
      mLong: null as number | null,
      mShort: null as number | null,
      mExit: null as number | null,
    }));
    // attach each marker to the nearest plotted bar (series is down-sampled)
    const times = base.map((r) => r.t);
    for (const m of data.markers) {
      let idx = times.findIndex((t) => t >= m.t);
      if (idx < 0) idx = base.length - 1;
      const row = base[idx];
      if (!row) continue;
      if (m.kind === "long") row.mLong = m.z;
      else if (m.kind === "short") row.mShort = m.z;
      else row.mExit = m.z;
    }
    return base;
  }, [data]);

  const zs = rows.map((r) => r.z).filter((z): z is number => z != null);
  const zMax = Math.max(3, ...zs.map((z) => Math.abs(z))) * 1.05;
  const tickFmt = (i: number) => rows[i]?.t?.slice(0, 7) ?? "";

  return (
    <ResponsiveContainer width="100%" height={360}>
      <ComposedChart data={rows} margin={{ top: 8, right: 14, left: -6, bottom: 0 }}>
        {/* extreme zones */}
        <ReferenceArea y1={2} y2={zMax} fill="#ef4444" fillOpacity={0.07} stroke="none" />
        <ReferenceArea y1={-zMax} y2={-2} fill="#22c55e" fillOpacity={0.07} stroke="none" />
        <CartesianGrid stroke="#27272a" strokeDasharray="2 4" vertical={false} />
        <XAxis
          dataKey="i"
          type="number"
          domain={[0, rows.length - 1]}
          tickFormatter={tickFmt}
          tick={{ fill: "#71717a", fontSize: 10 }}
          minTickGap={48}
          stroke="#3f3f46"
        />
        <YAxis
          domain={[-zMax, zMax]}
          tick={{ fill: "#71717a", fontSize: 10 }}
          stroke="#3f3f46"
          width={42}
          tickFormatter={(v) => (typeof v === "number" ? v.toFixed(1) : v)}
        />
        <ReferenceLine y={2} stroke="#ef4444" strokeDasharray="5 4" strokeOpacity={0.8}
          label={{ value: "+2σ  short", position: "right", fill: "#ef4444", fontSize: 10 }} />
        <ReferenceLine y={0} stroke="#a1a1aa" strokeDasharray="3 4" strokeOpacity={0.6} />
        <ReferenceLine y={-2} stroke="#22c55e" strokeDasharray="5 4" strokeOpacity={0.8}
          label={{ value: "-2σ  long", position: "right", fill: "#22c55e", fontSize: 10 }} />
        <Tooltip
          contentStyle={{ background: "#09090b", border: "1px solid #27272a", borderRadius: 8, fontSize: 12 }}
          labelStyle={{ color: "#a1a1aa" }}
          formatter={((val: unknown, name: unknown) => [
            typeof val === "number" ? val.toFixed(3) : String(val ?? ""),
            String(name ?? ""),
          ]) as never}
          labelFormatter={((i: unknown) => rows[Number(i)]?.t ?? "") as never}
        />
        <Line dataKey="z" name="Z-Score" stroke="#22d3ee" dot={false} strokeWidth={1.6} isAnimationActive={false} />
        <Scatter dataKey="mLong" name="Long-Entry" fill="#22c55e" shape="circle" isAnimationActive={false} />
        <Scatter dataKey="mShort" name="Short-Entry" fill="#ef4444" shape="circle" isAnimationActive={false} />
        <Scatter dataKey="mExit" name="Exit" fill="#38bdf8" shape="diamond" isAnimationActive={false} />
      </ComposedChart>
    </ResponsiveContainer>
  );
}
