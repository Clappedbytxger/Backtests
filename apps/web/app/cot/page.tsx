"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Bar,
  ComposedChart,
  Line,
  ReferenceArea,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  getCotAsset,
  getCotScan,
  getCotUniverse,
  type CotAssetResponse,
  type CotBias,
  type CotGroup,
  type CotMarket,
  type CotScanResponse,
} from "@/lib/api";

const cls = (...x: (string | false | undefined)[]) => x.filter(Boolean).join(" ");
const kfmt = (v: number | null | undefined) =>
  v == null ? "—" : `${v >= 0 ? "+" : ""}${(v / 1000).toFixed(0)}k`;
const WINDOWS = [
  { w: 156, label: "3J (156W)" },
  { w: 104, label: "2J (104W)" },
  { w: 260, label: "5J (260W)" },
];

const BIAS: Record<CotBias, { text: string; bg: string; border: string }> = {
  bullish: { text: "text-emerald-300", bg: "bg-emerald-500/15", border: "border-emerald-600/50" },
  bearish: { text: "text-red-300", bg: "bg-red-500/15", border: "border-red-600/50" },
  neutral: { text: "text-zinc-400", bg: "bg-zinc-700/20", border: "border-zinc-700" },
};
const GROUP_LABEL: Record<CotGroup, string> = {
  energy: "Energie", metal: "Metalle", grain: "Getreide",
  livestock: "Vieh", fx: "FX", index: "Indizes",
};

const AXIS_W = 64; // identical on all panels so the three charts line up vertically
const MARGIN = { top: 6, right: 16, bottom: 0, left: 0 };

export default function CotPage() {
  const [markets, setMarkets] = useState<CotMarket[]>([]);
  const [root, setRoot] = useState("GC");
  const [window, setWindow] = useState(156);
  const [osc, setOsc] = useState<"index" | "z">("index");
  const [asset, setAsset] = useState<CotAssetResponse | null>(null);
  const [scan, setScan] = useState<CotScanResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    getCotUniverse().then((r) => setMarkets(r.markets)).catch(() => {});
  }, []);

  const loadScan = useCallback((w: number) => {
    getCotScan(w).then(setScan).catch((e) => setError(String(e)));
  }, []);

  useEffect(() => {
    setLoading(true);
    setError(null);
    getCotAsset(root, window, window >= 260 ? 6 : 5)
      .then((r) => {
        if (!r.ok) throw new Error(r.error ?? "unknown");
        setAsset(r);
      })
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false));
  }, [root, window]);

  useEffect(() => loadScan(window), [window, loadScan]);

  const data = useMemo(() => asset?.rows ?? [], [asset]);
  const zones = asset?.zones ?? { index_low: 20, index_high: 80, extreme_z: 2 };

  return (
    <main className="mx-auto max-w-7xl px-6 py-6">
      <header className="mb-5 flex flex-wrap items-center gap-3">
        <div>
          <h1 className="text-lg font-semibold tracking-tight">Institutional Positioning Desk</h1>
          <p className="text-xs text-zinc-500">
            CFTC Commitments of Traders · Net Positions · COT-Index · 3-Jahres-Z-Score
          </p>
        </div>
        <div className="ml-auto flex flex-wrap items-center gap-2">
          <select
            value={root}
            onChange={(e) => setRoot(e.target.value)}
            className="rounded border border-zinc-700 bg-zinc-900 px-2 py-1.5 text-xs text-zinc-100"
          >
            {(["energy", "metal", "grain", "livestock", "fx", "index"] as CotGroup[]).map((g) => (
              <optgroup key={g} label={GROUP_LABEL[g]}>
                {markets.filter((m) => m.group === g).map((m) => (
                  <option key={m.root} value={m.root}>{m.name}</option>
                ))}
              </optgroup>
            ))}
          </select>
          <div className="flex overflow-hidden rounded border border-zinc-700">
            {WINDOWS.map((w) => (
              <button
                key={w.w}
                onClick={() => setWindow(w.w)}
                className={cls("px-2 py-1.5 text-xs", window === w.w ? "bg-zinc-700 text-zinc-100" : "bg-zinc-900 text-zinc-400 hover:bg-zinc-800")}
              >
                {w.label}
              </button>
            ))}
          </div>
        </div>
      </header>

      {error && (
        <div className="mb-4 rounded-lg border border-red-700/60 bg-red-950/40 px-4 py-2.5 text-sm text-red-300">
          {error}
        </div>
      )}

      {asset && <SignalBar asset={asset} />}

      {/* ── stacked charts ─────────────────────────────────────────────── */}
      <section className={cls("rounded-xl border border-zinc-800 bg-zinc-950", loading && "opacity-60")}>
        {/* Panel 1: price candles */}
        <Panel title={`${asset?.name ?? root} — Wochen-Chart`} sub={asset?.has_price ? asset.price_ticker : "kein Preis-Feed"}>
          <ResponsiveContainer width="100%" height={250}>
            <ComposedChart data={data} syncId="cot" margin={MARGIN}>
              <XAxis dataKey="t" hide />
              <YAxis
                width={AXIS_W}
                orientation="left"
                domain={["auto", "auto"]}
                tick={{ fill: "#71717a", fontSize: 10 }}
                axisLine={false}
                tickLine={false}
              />
              <Tooltip content={<CandleTip />} cursor={{ stroke: "#52525b", strokeDasharray: "3 3" }} />
              <Bar dataKey={(r: { low: number | null; high: number | null }) => (r.low != null && r.high != null ? [r.low, r.high] : null)} shape={<Candle />} isAnimationActive={false} />
            </ComposedChart>
          </ResponsiveContainer>
        </Panel>

        {/* Panel 2: net positions */}
        <Panel title="Netto-Positionierung" sub="Commercials (Smart Money) vs. Managed Money (Trendfolger)" border>
          <ResponsiveContainer width="100%" height={180}>
            <ComposedChart data={data} syncId="cot" margin={MARGIN}>
              <XAxis dataKey="t" hide />
              <YAxis
                width={AXIS_W}
                tickFormatter={(v) => `${(v / 1000).toFixed(0)}k`}
                tick={{ fill: "#71717a", fontSize: 10 }}
                axisLine={false}
                tickLine={false}
              />
              <ReferenceLine y={0} stroke="#71717a" strokeDasharray="4 3" />
              <Tooltip content={<NetTip />} cursor={{ stroke: "#52525b", strokeDasharray: "3 3" }} />
              <Line type="monotone" dataKey="comm_net" stroke="#3b82f6" dot={false} strokeWidth={1.6} isAnimationActive={false} name="Commercials" />
              <Line type="monotone" dataKey="noncomm_net" stroke="#22c55e" dot={false} strokeWidth={1.6} isAnimationActive={false} name="Managed Money" />
            </ComposedChart>
          </ResponsiveContainer>
        </Panel>

        {/* Panel 3: oscillator */}
        <Panel
          title={osc === "index" ? "COT-Index (Commercials)" : "COT Z-Score (Commercials)"}
          sub={osc === "index" ? "Extremzonen <20 / >80" : `Erschöpfung bei |z| > ${zones.extreme_z}`}
          border
          right={
            <div className="flex overflow-hidden rounded border border-zinc-700 text-[10px]">
              {(["index", "z"] as const).map((o) => (
                <button key={o} onClick={() => setOsc(o)} className={cls("px-2 py-1", osc === o ? "bg-zinc-700 text-zinc-100" : "bg-zinc-900 text-zinc-500 hover:bg-zinc-800")}>
                  {o === "index" ? "Index" : "Z-Score"}
                </button>
              ))}
            </div>
          }
        >
          <ResponsiveContainer width="100%" height={180}>
            <ComposedChart data={data} syncId="cot" margin={{ ...MARGIN, bottom: 4 }}>
              <XAxis dataKey="t" tick={{ fill: "#71717a", fontSize: 10 }} minTickGap={60} axisLine={false} tickLine={false} />
              <YAxis
                width={AXIS_W}
                domain={osc === "index" ? [0, 100] : [-3, 3]}
                tick={{ fill: "#71717a", fontSize: 10 }}
                axisLine={false}
                tickLine={false}
              />
              {osc === "index" ? (
                <>
                  <ReferenceArea y1={zones.index_high} y2={100} fill="#22c55e" fillOpacity={0.1} />
                  <ReferenceArea y1={0} y2={zones.index_low} fill="#ef4444" fillOpacity={0.1} />
                  <ReferenceLine y={50} stroke="#3f3f46" strokeDasharray="2 2" />
                  <Line type="monotone" dataKey="comm_index" stroke="#f59e0b" dot={false} strokeWidth={1.6} isAnimationActive={false} />
                </>
              ) : (
                <>
                  <ReferenceArea y1={zones.extreme_z} y2={3} fill="#22c55e" fillOpacity={0.1} />
                  <ReferenceArea y1={-3} y2={-zones.extreme_z} fill="#ef4444" fillOpacity={0.1} />
                  <ReferenceLine y={0} stroke="#3f3f46" strokeDasharray="2 2" />
                  <Line type="monotone" dataKey="comm_z" stroke="#f59e0b" dot={false} strokeWidth={1.6} isAnimationActive={false} />
                </>
              )}
              <Tooltip content={<OscTip kind={osc} />} cursor={{ stroke: "#52525b", strokeDasharray: "3 3" }} />
            </ComposedChart>
          </ResponsiveContainer>
        </Panel>
      </section>

      {/* ── extreme positioning table ──────────────────────────────────── */}
      <ExtremeTable scan={scan} active={root} onPick={setRoot} />
    </main>
  );
}

// ── signal summary bar ───────────────────────────────────────────────────────
function SignalBar({ asset }: { asset: CotAssetResponse }) {
  const l = asset.latest;
  const b = BIAS[l.signal.bias];
  return (
    <div className="mb-4 flex flex-wrap items-center gap-x-6 gap-y-2 rounded-xl border border-zinc-800 bg-zinc-900/40 px-5 py-3">
      <div className={cls("rounded-md border px-3 py-1.5 text-sm font-semibold", b.bg, b.border, b.text)}>
        {l.signal.status}
      </div>
      <Metric label="Commercials Net" value={kfmt(l.comm_net)} tone={l.comm_net >= 0 ? "pos" : "neg"} />
      <Metric label="Managed Money Net" value={kfmt(l.noncomm_net)} tone={l.noncomm_net >= 0 ? "pos" : "neg"} />
      <Metric label="COT-Index (Comm)" value={l.comm_index != null ? l.comm_index.toFixed(0) : "—"} />
      <Metric label="3J-Z-Score (Comm)" value={l.comm_z != null ? l.comm_z.toFixed(2) : "—"} tone={l.comm_z != null && Math.abs(l.comm_z) >= 2 ? (l.comm_z > 0 ? "pos" : "neg") : undefined} />
      <Metric label="Open Interest" value={`${(l.open_interest / 1000).toFixed(0)}k`} />
      <span className="ml-auto text-[10px] uppercase tracking-widest text-zinc-600">Stand {l.ref_date}</span>
    </div>
  );
}

function Metric({ label, value, tone }: { label: string; value: string; tone?: "pos" | "neg" }) {
  return (
    <div>
      <div className="text-[10px] uppercase tracking-widest text-zinc-600">{label}</div>
      <div className={cls("font-mono text-sm tabular-nums", tone === "pos" ? "text-emerald-300" : tone === "neg" ? "text-red-300" : "text-zinc-200")}>
        {value}
      </div>
    </div>
  );
}

function Panel({ title, sub, right, border, children }: { title: string; sub?: string; right?: React.ReactNode; border?: boolean; children: React.ReactNode }) {
  return (
    <div className={cls(border && "border-t border-zinc-800")}>
      <div className="flex items-center gap-2 px-4 pt-2.5">
        <span className="text-xs font-medium text-zinc-300">{title}</span>
        {sub && <span className="text-[10px] text-zinc-600">· {sub}</span>}
        {right && <div className="ml-auto">{right}</div>}
      </div>
      {children}
    </div>
  );
}

// ── candlestick custom shape (interpolates open/close inside the [low,high] band) ──
interface CandleProps {
  x?: number; y?: number; width?: number; height?: number;
  payload?: { open: number | null; high: number | null; low: number | null; close: number | null };
}
function Candle({ x = 0, y = 0, width = 0, height = 0, payload }: CandleProps) {
  if (!payload || payload.open == null || payload.high == null || payload.low == null || payload.close == null) return null;
  const { open, high, low, close } = payload;
  if (high === low) return null;
  const up = close >= open;
  const color = up ? "#22c55e" : "#ef4444";
  const ratio = height / (high - low); // px per price unit (top = high)
  const yTop = y + (high - Math.max(open, close)) * ratio;
  const yBot = y + (high - Math.min(open, close)) * ratio;
  const cx = x + width / 2;
  const bw = Math.max(2, width * 0.7);
  return (
    <g>
      <line x1={cx} y1={y} x2={cx} y2={y + height} stroke={color} strokeWidth={1} />
      <rect x={cx - bw / 2} y={yTop} width={bw} height={Math.max(1, yBot - yTop)} fill={color} />
    </g>
  );
}

// ── tooltips ─────────────────────────────────────────────────────────────────
interface TipProps {
  active?: boolean;
  payload?: { payload: CotAssetResponse["rows"][number] }[];
  label?: string;
}
function tipBox(label: string | undefined, lines: [string, string, string?][]) {
  return (
    <div className="rounded-md border border-zinc-700 bg-zinc-900/95 px-3 py-2 text-xs shadow-lg">
      <div className="mb-1 font-mono text-[10px] text-zinc-500">{label}</div>
      {lines.map(([k, v, c], i) => (
        <div key={i} className="flex justify-between gap-4">
          <span className="text-zinc-400">{k}</span>
          <span className={cls("font-mono tabular-nums", c ?? "text-zinc-200")}>{v}</span>
        </div>
      ))}
    </div>
  );
}
function CandleTip({ active, payload, label }: TipProps) {
  if (!active || !payload?.length) return null;
  const r = payload[0].payload;
  if (r.close == null) return tipBox(label, [["Preis", "kein Feed"]]);
  return tipBox(label, [
    ["O", r.open!.toFixed(2)], ["H", r.high!.toFixed(2)],
    ["L", r.low!.toFixed(2)], ["C", r.close.toFixed(2), r.close >= (r.open ?? 0) ? "text-emerald-300" : "text-red-300"],
  ]);
}
function NetTip({ active, payload, label }: TipProps) {
  if (!active || !payload?.length) return null;
  const r = payload[0].payload;
  return tipBox(label, [
    ["Commercials", kfmt(r.comm_net), "text-blue-300"],
    ["Managed Money", kfmt(r.noncomm_net), "text-emerald-300"],
  ]);
}
function OscTip({ active, payload, label, kind }: TipProps & { kind: "index" | "z" }) {
  if (!active || !payload?.length) return null;
  const r = payload[0].payload;
  return tipBox(label, kind === "index"
    ? [["COT-Index", r.comm_index != null ? r.comm_index.toFixed(1) : "—", "text-amber-300"]]
    : [["Z-Score", r.comm_z != null ? r.comm_z.toFixed(2) : "—", "text-amber-300"]]);
}

// ── extreme positioning table ─────────────────────────────────────────────────
function ExtremeTable({ scan, active, onPick }: { scan: CotScanResponse | null; active: string; onPick: (r: string) => void }) {
  return (
    <section className="mt-6 overflow-hidden rounded-xl border border-zinc-800">
      <div className="flex items-center gap-2 border-b border-zinc-800 bg-zinc-900/60 px-4 py-2.5">
        <h2 className="text-sm font-semibold">Extreme Positioning</h2>
        <span className="text-[10px] uppercase tracking-widest text-zinc-600">sortiert nach |Commercial Z-Score|</span>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-right text-xs">
          <thead className="bg-zinc-900/40 text-[10px] uppercase tracking-wide text-zinc-500">
            <tr>
              <th className="px-4 py-2 text-left">Asset</th>
              <th className="px-3 py-2 text-left">Gruppe</th>
              <th className="px-3 py-2">Commercial Net</th>
              <th className="px-3 py-2">Managed Money Net</th>
              <th className="px-3 py-2">COT-Index</th>
              <th className="px-3 py-2">3J-Z-Score</th>
              <th className="px-4 py-2 text-left">Signal</th>
            </tr>
          </thead>
          <tbody>
            {!scan && (
              <tr><td colSpan={7} className="px-4 py-8 text-center text-zinc-600">Lade Scan …</td></tr>
            )}
            {scan?.markets.map((m) => {
              const b = BIAS[m.signal.bias];
              const extreme = m.comm_z != null && Math.abs(m.comm_z) >= (scan.zones.extreme_z ?? 2);
              return (
                <tr
                  key={m.root}
                  onClick={() => onPick(m.root)}
                  className={cls(
                    "cursor-pointer border-b border-zinc-900 transition-colors hover:bg-zinc-900/50",
                    m.root === active && "bg-zinc-800/40",
                  )}
                >
                  <td className="px-4 py-2 text-left">
                    <span className="font-medium text-zinc-100">{m.name}</span>
                    <span className="ml-1.5 font-mono text-[10px] text-zinc-600">{m.root}</span>
                  </td>
                  <td className="px-3 py-2 text-left text-zinc-500">{GROUP_LABEL[m.group]}</td>
                  <td className={cls("px-3 py-2 font-mono tabular-nums", m.comm_net >= 0 ? "text-emerald-300/90" : "text-red-300/90")}>{kfmt(m.comm_net)}</td>
                  <td className={cls("px-3 py-2 font-mono tabular-nums", m.noncomm_net >= 0 ? "text-emerald-300/90" : "text-red-300/90")}>{kfmt(m.noncomm_net)}</td>
                  <td className="px-3 py-2">
                    <IndexCell value={m.comm_index} low={scan.zones.index_low} high={scan.zones.index_high} />
                  </td>
                  <td className={cls("px-3 py-2 font-mono tabular-nums font-semibold", extreme ? (m.comm_z! > 0 ? "text-emerald-300" : "text-red-300") : "text-zinc-400")}>
                    {m.comm_z != null ? `${m.comm_z > 0 ? "+" : ""}${m.comm_z.toFixed(2)}` : "—"}
                  </td>
                  <td className="px-4 py-2 text-left">
                    <span className={cls("rounded border px-1.5 py-0.5 text-[10px]", b.bg, b.border, b.text)}>{m.signal.status}</span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function IndexCell({ value, low, high }: { value: number; low: number; high: number }) {
  const color = value >= high ? "#22c55e" : value <= low ? "#ef4444" : "#52525b";
  return (
    <div className="flex items-center justify-end gap-2">
      <div className="relative h-1.5 w-16 overflow-hidden rounded bg-zinc-800">
        <div className="absolute inset-y-0 left-0 rounded" style={{ width: `${value}%`, background: color }} />
      </div>
      <span className="w-7 font-mono tabular-nums text-zinc-300">{value.toFixed(0)}</span>
    </div>
  );
}
