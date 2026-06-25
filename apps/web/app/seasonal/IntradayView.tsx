"use client";

import { useEffect, useMemo, useState } from "react";
import {
  Bar,
  Cell,
  ComposedChart,
  CartesianGrid,
  Line,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  getIntraday,
  getIntradayInstruments,
  type IntradayInstrument,
  type IntradayResponse,
} from "@/lib/api";

const AXIS = { fill: "#71717a", fontSize: 10 };
const GRID = "#27272a";
const TOOLTIP = { background: "#18181b", border: "1px solid #3f3f46", borderRadius: 8, fontSize: 12, color: "#e4e4e7" };
const CLASS_LABEL: Record<string, string> = { futures: "Futures", equities: "Aktien", crypto: "Krypto", other: "Sonstige" };
const bps = (x: number) => `${x >= 0 ? "+" : ""}${x.toFixed(1)} bps`;

/** Diverging green/red background for a bps cell, opacity scaled to the grid cap. */
function cell(v: number | null, cap: number): React.CSSProperties {
  if (v == null) return { background: "transparent" };
  const a = Math.min(1, Math.abs(v) / cap) * 0.85 + 0.05;
  return v >= 0 ? { background: `rgba(16,185,129,${a})` } : { background: `rgba(239,68,68,${a})` };
}

export default function IntradayView() {
  const [instruments, setInstruments] = useState<IntradayInstrument[]>([]);
  const [ticker, setTicker] = useState("AAPL");
  const [rth, setRth] = useState(true);
  const [data, setData] = useState<IntradayResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getIntradayInstruments().then((d) => d.ok && setInstruments(d.instruments)).catch(() => {});
  }, []);

  useEffect(() => {
    if (!ticker) return;
    setLoading(true);
    setError(null);
    getIntraday(ticker, 8, rth)
      .then((d) => {
        if (!d.ok) throw new Error(d.error || "intraday failed");
        setData(d);
      })
      .catch((e) => setError(String(e.message || e)))
      .finally(() => setLoading(false));
  }, [ticker, rth]);

  const groups = useMemo(() => {
    const g: Record<string, IntradayInstrument[]> = {};
    for (const i of instruments) (g[i.asset_class] ??= []).push(i);
    return g;
  }, [instruments]);

  const isCrypto = data?.meta.asset_class === "crypto";

  const heatCap = useMemo(() => {
    if (!data) return 1;
    const vals = data.heatmap.matrix.flat().filter((v): v is number => v != null).map(Math.abs).sort((a, b) => a - b);
    if (!vals.length) return 1;
    return Math.max(vals[Math.floor(vals.length * 0.9)] ?? 1, 1);
  }, [data]);

  const hourLabel = (h: number) => `${String(h).padStart(2, "0")}:00`;

  return (
    <div>
      {/* instrument selector */}
      <div className="mb-5 space-y-2">
        {Object.entries(groups).map(([cls, items]) => (
          <div key={cls} className="flex items-start gap-3">
            <span className="w-16 shrink-0 pt-1 text-[11px] uppercase tracking-wide text-zinc-500">{CLASS_LABEL[cls] ?? cls}</span>
            <div className="flex flex-1 flex-wrap gap-1.5">
              {items.map((i) => (
                <button
                  key={i.ticker}
                  onClick={() => setTicker(i.ticker)}
                  className={`rounded-md border px-2 py-0.5 text-xs font-medium transition ${
                    ticker === i.ticker
                      ? "border-sky-600 bg-sky-950/60 text-sky-200"
                      : "border-zinc-800 bg-zinc-900/50 text-zinc-400 hover:border-zinc-600 hover:text-zinc-200"
                  }`}
                  title={i.name}
                >
                  {i.ticker}
                </button>
              ))}
            </div>
          </div>
        ))}
      </div>

      {error && (
        <div className="mb-4 rounded-lg border border-red-900 bg-red-950/40 px-4 py-3 text-sm text-red-300">{error}</div>
      )}

      {data && (
        <>
          <div className="mb-4 flex flex-wrap items-baseline justify-between gap-2">
            <h2 className="text-xl font-semibold">
              {data.meta.name} <span className="font-mono text-sm text-zinc-500">{data.ticker}</span>
              <span className="ml-2 rounded border border-zinc-700 px-1.5 py-0.5 text-[10px] uppercase text-zinc-400">
                {data.meta.native_tf} · {data.tz}
              </span>
            </h2>
            <div className="flex items-center gap-3 text-xs text-zinc-500">
              <span>{data.span.start} – {data.span.end} · {data.span.n_days} Tage</span>
              {!isCrypto && (
                <label className="flex items-center gap-1.5 text-zinc-400">
                  <input type="checkbox" checked={rth} onChange={(e) => setRth(e.target.checked)} className="accent-sky-500" />
                  nur RTH (09:30–16:00)
                </label>
              )}
            </div>
          </div>

          {/* ── Hour-of-day profile (bars = per-hour mean, line = average day) ── */}
          <section className="mb-6 rounded-xl border border-zinc-800 bg-zinc-900/40 p-5">
            <h3 className="mb-3 text-sm font-semibold text-zinc-200">Tageszeit-Profil (Ø je Stunde + kumulierter Durchschnittstag)</h3>
            <ResponsiveContainer width="100%" height={300}>
              <ComposedChart data={data.hours} margin={{ top: 5, right: 10, left: -8, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
                <XAxis dataKey="hour" tickFormatter={hourLabel} tick={AXIS} />
                <YAxis yAxisId="l" tick={AXIS} width={46} tickFormatter={(v) => `${v}`} label={{ value: "Ø bps/Std.", angle: -90, position: "insideLeft", fill: "#71717a", fontSize: 10 }} />
                <YAxis yAxisId="r" orientation="right" tick={AXIS} width={46} tickFormatter={(v) => `${v}`} />
                <Tooltip
                  contentStyle={TOOLTIP}
                  labelFormatter={(h) => `${hourLabel(Number(h))} – ${hourLabel(Number(h) + 1)}`}
                  formatter={(v, n) => [bps(Number(v)), n === "cum_bps" ? "Ø Tag kumuliert" : "Ø Stunde"]}
                />
                <ReferenceLine yAxisId="l" y={0} stroke="#52525b" />
                <Bar yAxisId="l" dataKey="mean_bps" isAnimationActive={false} radius={[2, 2, 0, 0]}>
                  {data.hours.map((h, i) => (
                    <Cell key={i} fill={h.mean_bps >= 0 ? "#10b981" : "#ef4444"} fillOpacity={h.p_value < 0.05 ? 0.95 : 0.45} />
                  ))}
                </Bar>
                <Line yAxisId="r" type="monotone" dataKey="cum_bps" stroke="#38bdf8" strokeWidth={2} dot={false} isAnimationActive={false} />
              </ComposedChart>
            </ResponsiveContainer>
            <p className="mt-1 text-[11px] text-zinc-500">
              Balken = durchschnittliche Rendite während jeder {data.tz}-Stunde (close/open des Stundenbalkens, volle
              Sättigung = p&lt;0,05). Blaue Linie = kumulierter „Durchschnittstag". {isCrypto ? "24h-Markt." : "Stunde 09 = Eröffnungs-Halbstunde 09:30–10:00."}
            </p>
          </section>

          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            {/* ── Weekday profile ──────────────────────────────────────────── */}
            <section className="rounded-xl border border-zinc-800 bg-zinc-900/40 p-5">
              <h3 className="mb-3 text-sm font-semibold text-zinc-200">Wochentag-Profil (Ø Session-Rendite)</h3>
              <ResponsiveContainer width="100%" height={220}>
                <ComposedChart data={data.weekdays} margin={{ top: 5, right: 6, left: -8, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
                  <XAxis dataKey="name" tick={AXIS} />
                  <YAxis tick={AXIS} width={46} />
                  <Tooltip
                    contentStyle={TOOLTIP}
                    formatter={(v, _n, item) => {
                      const pl = (item?.payload ?? {}) as { hit_rate?: number; p_value?: number };
                      return [`${bps(Number(v))} (WR ${((pl.hit_rate ?? 0) * 100).toFixed(0)}%, p=${(pl.p_value ?? 1).toFixed(2)})`, "Ø Tag"];
                    }}
                  />
                  <ReferenceLine y={0} stroke="#52525b" />
                  <Bar dataKey="mean_bps" isAnimationActive={false} radius={[2, 2, 0, 0]}>
                    {data.weekdays.map((w, i) => (
                      <Cell key={i} fill={w.mean_bps >= 0 ? "#10b981" : "#ef4444"} fillOpacity={w.p_value < 0.05 ? 0.95 : 0.45} />
                    ))}
                  </Bar>
                </ComposedChart>
              </ResponsiveContainer>
              <p className="mt-1 text-[11px] text-zinc-500">Session-Rendite (close/open je Tag) gemittelt je Wochentag.</p>
            </section>

            {/* ── Weekday × hour heatmap ───────────────────────────────────── */}
            <section className="rounded-xl border border-zinc-800 bg-zinc-900/40 p-5">
              <h3 className="mb-3 text-sm font-semibold text-zinc-200">Heatmap Wochentag × Stunde (Ø bps)</h3>
              <div className="overflow-x-auto">
                <table className="w-full border-separate border-spacing-0.5 text-[10px]">
                  <thead>
                    <tr className="text-zinc-500">
                      <th className="px-1 py-0.5 text-left font-medium">Tag</th>
                      {data.heatmap.hours.map((h) => (
                        <th key={h} className="px-0.5 py-0.5 text-center font-medium">{String(h).padStart(2, "0")}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {data.heatmap.weekdays.map((wd, ri) => (
                      <tr key={wd}>
                        <td className="px-1 py-0.5 font-medium text-zinc-400">{wd}</td>
                        {data.heatmap.matrix[ri].map((v, ci) => (
                          <td
                            key={ci}
                            className="px-0.5 py-1 text-center font-mono tabular-nums text-zinc-100"
                            style={cell(v, heatCap)}
                            title={v == null ? "–" : `${wd} ${String(data.heatmap.hours[ci]).padStart(2, "0")}:00 → ${bps(v)}`}
                          >
                            {v == null ? "" : v.toFixed(0)}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <p className="mt-2 text-[11px] text-zinc-500">Grün/Rot = Ø Rendite (bps) je Wochentag-Stunde-Kombination.</p>
            </section>
          </div>

          <p className="mt-5 rounded-lg border border-amber-900/50 bg-amber-950/20 px-4 py-3 text-[12px] text-amber-200/80">
            <b>Ehrlichkeits-Hinweis:</b> Dies sind <b>Brutto-</b>Struktur-Profile. Die Repo-Befunde (Strategien
            0038–0041) zeigen, dass die <i>Intraday-Richtung</i> eines einzelnen liquiden Marktes netto nach Kosten
            nicht handelbar ist — diese Ansichten dienen dem Verständnis der Mikrostruktur, nicht als eigenständiger Edge.
          </p>
        </>
      )}

      {loading && !data && <p className="text-sm text-zinc-500">Lade Intraday-Daten …</p>}
    </div>
  );
}
