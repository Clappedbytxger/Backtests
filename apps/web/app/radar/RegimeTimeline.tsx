"use client";

import { useMemo } from "react";
import {
  CartesianGrid,
  ComposedChart,
  Line,
  ReferenceArea,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { RegimeCode, RegimeTimelineResponse } from "@/lib/api";

const LABELS: Record<RegimeCode, string> = {
  high_vol_trend: "High Vol · Trending",
  low_vol_trend: "Low Vol · Trending",
  high_vol_range: "High Vol · Choppy",
  low_vol_range: "Low Vol · Quiet",
};

/**
 * Price line with the chart background shaded EXACTLY by market regime — the core
 * "you can see the weather change" view. Shaded spans are recomputed from the
 * (down-sampled) price points themselves so boundaries always align with the axis.
 */
export default function RegimeTimeline({ data }: { data: RegimeTimelineResponse }) {
  const rows = useMemo(
    () => data.price.map((p, i) => ({ ...p, i })),
    [data.price],
  );

  // contiguous index-ranges of equal regime, aligned to the plotted points
  const spans = useMemo(() => {
    const out: { r: RegimeCode; x1: number; x2: number }[] = [];
    let cur: RegimeCode | null = null;
    let start = 0;
    rows.forEach((p, i) => {
      const r = (p.regime ?? null) as RegimeCode | null;
      if (r !== cur) {
        if (cur) out.push({ r: cur, x1: start, x2: i });
        cur = r;
        start = i;
      }
    });
    if (cur) out.push({ r: cur, x1: start, x2: rows.length - 1 });
    return out;
  }, [rows]);

  const palette = data.palette;
  const tickFmt = (i: number) => rows[i]?.t?.slice(0, 7) ?? "";

  return (
    <div>
      <ResponsiveContainer width="100%" height={340}>
        <ComposedChart data={rows} margin={{ top: 8, right: 12, left: -6, bottom: 0 }}>
          {spans.map((s, k) => (
            <ReferenceArea
              key={k}
              x1={s.x1}
              x2={s.x2}
              y1={undefined}
              y2={undefined}
              fill={palette[s.r]}
              fillOpacity={0.16}
              stroke="none"
              ifOverflow="extendDomain"
            />
          ))}
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
            domain={["auto", "auto"]}
            tick={{ fill: "#71717a", fontSize: 10 }}
            stroke="#3f3f46"
            width={52}
            tickFormatter={(v) => (typeof v === "number" ? v.toFixed(0) : v)}
          />
          <Tooltip
            contentStyle={{
              background: "#09090b",
              border: "1px solid #27272a",
              borderRadius: 8,
              fontSize: 12,
            }}
            labelStyle={{ color: "#a1a1aa" }}
            formatter={((val: unknown, name: unknown) => [
              typeof val === "number" ? val.toFixed(2) : String(val ?? ""),
              String(name ?? ""),
            ]) as never}
            labelFormatter={((i: unknown) => {
              const p = rows[Number(i)];
              const r = p?.regime as RegimeCode | null;
              return `${p?.t ?? ""}${r ? "  ·  " + LABELS[r] : ""}`;
            }) as never}
          />
          <Line dataKey="sma_slow" name="SMA200" stroke="#3b82f6" dot={false} strokeWidth={1} strokeOpacity={0.7} isAnimationActive={false} />
          <Line dataKey="sma_mid" name="SMA50" stroke="#a78bfa" dot={false} strokeWidth={1} strokeOpacity={0.6} isAnimationActive={false} />
          <Line dataKey="ema_fast" name="EMA20" stroke="#f59e0b" dot={false} strokeWidth={1} strokeOpacity={0.55} isAnimationActive={false} />
          <Line dataKey="close" name="Close" stroke="#fafafa" dot={false} strokeWidth={1.7} isAnimationActive={false} />
        </ComposedChart>
      </ResponsiveContainer>
      <div className="mt-3 flex flex-wrap gap-x-5 gap-y-1.5">
        {(Object.keys(LABELS) as RegimeCode[]).map((c) => (
          <span key={c} className="flex items-center gap-1.5 text-[11px] text-zinc-400">
            <span className="h-2.5 w-2.5 rounded-sm" style={{ background: palette[c] }} />
            {LABELS[c]}
          </span>
        ))}
      </div>
    </div>
  );
}
