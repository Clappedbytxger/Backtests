"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Bar,
  BarChart,
  Cell,
  CartesianGrid,
  ComposedChart,
  Area,
  Line,
  ReferenceArea,
  ReferenceLine,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
  ZAxis,
} from "recharts";
import {
  getAttribBook,
  getAttribBrinson,
  getAttribFactors,
  getAttribRolling,
  type AttribBook,
  type AttribBrinson,
  type AttribFactors,
  type AttribRolling,
  type FactorPoint,
  type Quadrant,
} from "@/lib/api";

const cls = (...x: (string | false | undefined)[]) => x.filter(Boolean).join(" ");
const pct = (v: number | null | undefined, d = 2) =>
  v == null ? "—" : `${v >= 0 ? "+" : ""}${(v * 100).toFixed(d)}%`;

const QUAD: Record<Quadrant, { color: string; label: string }> = {
  premium: { color: "#22c55e", label: "Premium (High α / Low β)" },
  leveraged: { color: "#38bdf8", label: "Leveraged (High α / High β)" },
  defensive: { color: "#a1a1aa", label: "Defensive (Low α / Low β)" },
  closet_beta: { color: "#ef4444", label: "Closet Beta (Low α / High β)" },
};

export default function AttributionPage() {
  const [book, setBook] = useState<AttribBook | null>(null);
  const [benchmark, setBenchmark] = useState("SPY");
  const [window, setWindow] = useState("full");
  const [rollWindow, setRollWindow] = useState(63);
  const [rollNum, setRollNum] = useState("PORTFOLIO");
  const [factors, setFactors] = useState<AttribFactors | null>(null);
  const [rolling, setRolling] = useState<AttribRolling | null>(null);
  const [brinson, setBrinson] = useState<AttribBrinson | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getAttribBook().then(setBook).catch((e) => setError(String(e)));
  }, []);

  useEffect(() => {
    getAttribFactors(benchmark, window).then(setFactors).catch((e) => setError(String(e)));
  }, [benchmark, window]);

  const loadRolling = useCallback(() => {
    getAttribRolling(rollNum, benchmark, rollWindow).then(setRolling).catch(() => setRolling(null));
  }, [rollNum, benchmark, rollWindow]);
  useEffect(() => loadRolling(), [loadRolling]);

  useEffect(() => {
    getAttribBrinson(window === "full" ? "1260" : window).then(setBrinson).catch(() => setBrinson(null));
  }, [window]);

  return (
    <main className="mx-auto max-w-7xl px-6 py-6">
      <header className="mb-5 flex flex-wrap items-center gap-3 border-b border-zinc-800 pb-4">
        <div>
          <h1 className="font-mono text-lg font-semibold tracking-tight text-zinc-100">
            ATTRIBUTION DESK
          </h1>
          <p className="text-xs text-zinc-500">
            Skill vs. Market · CAPM α/β Regression · Brinson-Fachler Decomposition
          </p>
        </div>
        <div className="ml-auto flex flex-wrap items-center gap-2">
          <Toggle
            label="Benchmark"
            value={benchmark}
            options={(book?.benchmarks ?? [{ key: "SPY", label: "SPY" }]).map((b) => ({ k: b.key, l: b.key }))}
            onChange={setBenchmark}
          />
          <Toggle
            label="Fenster"
            value={window}
            options={(book?.windows ?? [{ key: "full", label: "Gesamt" }]).map((w) => ({ k: w.key, l: w.label }))}
            onChange={setWindow}
          />
        </div>
      </header>

      {error && (
        <div className="mb-4 rounded border border-red-700/60 bg-red-950/40 px-4 py-2.5 text-sm text-red-300">
          {error}
        </div>
      )}

      <PortfolioVerdict factors={factors} brinson={brinson} />

      {/* waterfall + scatter side by side */}
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        <BrinsonWaterfall brinson={brinson} />
        <AlphaBetaScatter factors={factors} />
      </div>

      {/* rolling alpha/beta */}
      <RollingChart
        rolling={rolling}
        book={book}
        rollNum={rollNum}
        setRollNum={setRollNum}
        rollWindow={rollWindow}
        setRollWindow={setRollWindow}
      />

      {/* brinson sector table */}
      <BrinsonTable brinson={brinson} />
    </main>
  );
}

function Toggle({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: string;
  options: { k: string; l: string }[];
  onChange: (v: string) => void;
}) {
  return (
    <div className="flex items-center gap-1.5">
      <span className="text-[10px] uppercase tracking-widest text-zinc-600">{label}</span>
      <div className="flex overflow-hidden rounded border border-zinc-700">
        {options.map((o) => (
          <button
            key={o.k}
            onClick={() => onChange(o.k)}
            className={cls(
              "px-2 py-1 text-xs",
              value === o.k ? "bg-zinc-700 text-zinc-100" : "bg-zinc-900 text-zinc-400 hover:bg-zinc-800",
            )}
          >
            {o.l}
          </button>
        ))}
      </div>
    </div>
  );
}

// ── portfolio verdict bar ───────────────────────────────────────────────────────
function PortfolioVerdict({ factors, brinson }: { factors: AttribFactors | null; brinson: AttribBrinson | null }) {
  const p = factors?.portfolio;
  const skillVerdict =
    p == null
      ? "—"
      : p.beta < 0.3 && p.alpha_annual > 0 && p.p_alpha < 0.05
        ? "ALPHA-DRIVEN (Skill)"
        : p.beta >= 0.7
          ? "BETA-DRIVEN (Markt)"
          : "MIXED";
  const tone =
    skillVerdict.startsWith("ALPHA") ? "pos" : skillVerdict.startsWith("BETA") ? "neg" : "neu";
  return (
    <div className="mb-4 flex flex-wrap items-center gap-x-8 gap-y-2 rounded border border-zinc-800 bg-zinc-900/40 px-5 py-3 font-mono">
      <div
        className={cls(
          "rounded border px-3 py-1.5 text-sm font-bold tracking-wide",
          tone === "pos" ? "border-emerald-600/50 bg-emerald-500/15 text-emerald-300"
            : tone === "neg" ? "border-red-600/50 bg-red-500/15 text-red-300"
              : "border-zinc-600 bg-zinc-700/20 text-zinc-300",
        )}
      >
        {skillVerdict}
      </div>
      <Metric label="Portfolio α (p.a.)" value={pct(p?.alpha_annual)} tone={(p?.alpha_annual ?? 0) > 0 ? "pos" : "neg"} />
      <Metric label="Portfolio β" value={p?.beta != null ? p.beta.toFixed(3) : "—"}
        tone={p?.beta != null && Math.abs(p.beta) < 0.3 ? "pos" : undefined} />
      <Metric label="α t-Stat" value={p?.t_alpha != null ? p.t_alpha.toFixed(1) : "—"}
        tone={(p?.t_alpha ?? 0) > 2 ? "pos" : undefined} />
      <Metric label="α p-Value" value={p?.p_alpha != null ? p.p_alpha.toFixed(3) : "—"} />
      <Metric label="R²" value={p?.r_squared != null ? p.r_squared.toFixed(3) : "—"} />
      {brinson && (
        <Metric label="Active Return" value={pct(brinson.active_return)} tone={brinson.active_return >= 0 ? "pos" : "neg"} />
      )}
    </div>
  );
}

function Metric({ label, value, tone }: { label: string; value: string; tone?: "pos" | "neg" }) {
  return (
    <div>
      <div className="text-[10px] uppercase tracking-widest text-zinc-600">{label}</div>
      <div className={cls("text-sm tabular-nums", tone === "pos" ? "text-emerald-300" : tone === "neg" ? "text-red-300" : "text-zinc-200")}>
        {value}
      </div>
    </div>
  );
}

// ── Brinson waterfall ───────────────────────────────────────────────────────────
function BrinsonWaterfall({ brinson }: { brinson: AttribBrinson | null }) {
  const data = useMemo(() => {
    if (!brinson) return [];
    return brinson.waterfall.map((s) => {
      if (s.kind === "start" || s.kind === "end") {
        return { label: s.label, base: 0, bar: s.cumulative, value: s.value, fill: "#60a5fa", kind: s.kind };
      }
      const lo = Math.min(s.base ?? 0, s.cumulative);
      return {
        label: s.label,
        base: lo,
        bar: Math.abs(s.value),
        value: s.value,
        fill: s.value >= 0 ? "#22c55e" : "#ef4444",
        kind: s.kind,
      };
    });
  }, [brinson]);

  return (
    <section className="overflow-hidden rounded border border-zinc-800 bg-zinc-950">
      <PanelHead title="Brinson-Fachler Waterfall" sub="Benchmark → Allokation → Selektion → Interaktion → Portfolio" />
      <div className="px-2 pb-3 pt-2">
        {data.length === 0 ? (
          <Empty />
        ) : (
          <>
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={data} margin={{ top: 8, right: 16, bottom: 4, left: 4 }}>
                <CartesianGrid stroke="#27272a" strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="label" tick={{ fill: "#a1a1aa", fontSize: 10 }} axisLine={false} tickLine={false} />
                <YAxis tickFormatter={(v) => `${(v * 100).toFixed(0)}%`} tick={{ fill: "#71717a", fontSize: 10 }} axisLine={false} tickLine={false} />
                <ReferenceLine y={0} stroke="#52525b" />
                <Tooltip
                  cursor={{ fill: "#27272a55" }}
                  contentStyle={{ background: "#18181b", border: "1px solid #3f3f46", borderRadius: 6, fontSize: 12 }}
                  formatter={(_v, _n, item) => {
                    const pl = item?.payload as { value: number; kind: string };
                    return [`${pl.value >= 0 ? "+" : ""}${(pl.value * 100).toFixed(2)}%`, pl.kind === "effect" ? "Effekt" : "Niveau"];
                  }}
                />
                <Bar dataKey="base" stackId="w" fill="transparent" isAnimationActive={false} />
                <Bar dataKey="bar" stackId="w" isAnimationActive={false} radius={[2, 2, 0, 0]}>
                  {data.map((d, i) => (
                    <Cell key={i} fill={d.fill} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
            {brinson && (
              <p className="px-3 pt-1 text-[10px] text-zinc-600">
                Identitäts-Check: Σ(Effekte) − Active Return = {brinson.residual.toExponential(1)} ≈ 0 ·{" "}
                {brinson.n_sectors_with_benchmark}/{brinson.n_sectors} Sektoren mit Benchmark
              </p>
            )}
          </>
        )}
      </div>
    </section>
  );
}

// ── alpha vs beta scatter ───────────────────────────────────────────────────────
function AlphaBetaScatter({ factors }: { factors: AttribFactors | null }) {
  const pts = factors?.points ?? [];
  const groups = useMemo(() => {
    const g: Record<Quadrant, FactorPoint[]> = { premium: [], leveraged: [], defensive: [], closet_beta: [] };
    pts.forEach((p) => g[p.quadrant].push(p));
    return g;
  }, [pts]);
  const betas = pts.map((p) => p.beta);
  const xMin = Math.min(-0.2, ...betas) - 0.1;
  const xMax = Math.max(1.0, ...betas) + 0.1;
  const alphas = pts.map((p) => p.alpha_annual);
  const yAbs = Math.max(0.05, ...alphas.map(Math.abs)) * 1.2;

  return (
    <section className="overflow-hidden rounded border border-zinc-800 bg-zinc-950">
      <PanelHead title="Alpha vs. Beta" sub="4-Quadranten · oben-links = Premium-Strategien" />
      <div className="px-2 pb-3 pt-2">
        {pts.length === 0 ? (
          <Empty />
        ) : (
          <ResponsiveContainer width="100%" height={300}>
            <ScatterChart margin={{ top: 12, right: 16, bottom: 16, left: 4 }}>
              {/* premium quadrant highlight: beta<0.5, alpha>0 */}
              <ReferenceArea x1={xMin} x2={0.5} y1={0} y2={yAbs} fill="#22c55e" fillOpacity={0.06} />
              <CartesianGrid stroke="#27272a" strokeDasharray="3 3" />
              <XAxis
                type="number"
                dataKey="beta"
                name="Beta"
                domain={[xMin, xMax]}
                tick={{ fill: "#71717a", fontSize: 10 }}
                axisLine={false}
                tickLine={false}
                label={{ value: "β (Markt-Sensitivität)", position: "insideBottom", offset: -8, fill: "#71717a", fontSize: 10 }}
              />
              <YAxis
                type="number"
                dataKey="alpha_annual"
                name="Alpha"
                domain={[-yAbs, yAbs]}
                tickFormatter={(v) => `${(v * 100).toFixed(0)}%`}
                tick={{ fill: "#71717a", fontSize: 10 }}
                axisLine={false}
                tickLine={false}
                label={{ value: "α p.a.", angle: -90, position: "insideLeft", fill: "#71717a", fontSize: 10 }}
              />
              <ZAxis range={[60, 60]} />
              <ReferenceLine x={0.5} stroke="#52525b" strokeDasharray="4 3" />
              <ReferenceLine y={0} stroke="#52525b" strokeDasharray="4 3" />
              <Tooltip cursor={{ strokeDasharray: "3 3" }} content={<ScatterTip />} />
              {(Object.keys(groups) as Quadrant[]).map((q) => (
                <Scatter key={q} data={groups[q]} fill={QUAD[q].color} isAnimationActive={false} />
              ))}
              {factors?.portfolio && (
                <Scatter
                  data={[{ beta: factors.portfolio.beta, alpha_annual: factors.portfolio.alpha_annual, label: "PORTFOLIO", name: "Portfolio", quadrant: factors.portfolio.quadrant }]}
                  fill="#fbbf24"
                  shape="star"
                  isAnimationActive={false}
                />
              )}
            </ScatterChart>
          </ResponsiveContainer>
        )}
        <div className="flex flex-wrap gap-x-4 gap-y-1 px-3 pt-1">
          {(Object.keys(QUAD) as Quadrant[]).map((q) => (
            <span key={q} className="inline-flex items-center gap-1.5 text-[10px] text-zinc-500">
              <span className="h-2 w-2 rounded-full" style={{ background: QUAD[q].color }} />
              {QUAD[q].label}
            </span>
          ))}
          <span className="inline-flex items-center gap-1.5 text-[10px] text-amber-400">★ Portfolio</span>
        </div>
      </div>
    </section>
  );
}

interface ScatterTipProps {
  active?: boolean;
  payload?: { payload: FactorPoint & { name?: string } }[];
}
function ScatterTip({ active, payload }: ScatterTipProps) {
  if (!active || !payload?.length) return null;
  const p = payload[0].payload;
  return (
    <div className="rounded border border-zinc-700 bg-zinc-900/95 px-3 py-2 text-xs shadow-lg">
      <div className="mb-1 font-medium text-zinc-100">{p.name ?? p.label}</div>
      <div className="flex justify-between gap-4"><span className="text-zinc-400">α p.a.</span><span className="font-mono text-emerald-300">{pct(p.alpha_annual)}</span></div>
      <div className="flex justify-between gap-4"><span className="text-zinc-400">β</span><span className="font-mono text-zinc-200">{p.beta?.toFixed(3)}</span></div>
      {p.p_alpha != null && <div className="flex justify-between gap-4"><span className="text-zinc-400">p(α)</span><span className="font-mono text-zinc-200">{p.p_alpha.toFixed(3)}</span></div>}
    </div>
  );
}

// ── rolling alpha/beta ──────────────────────────────────────────────────────────
function RollingChart({
  rolling,
  book,
  rollNum,
  setRollNum,
  rollWindow,
  setRollWindow,
}: {
  rolling: AttribRolling | null;
  book: AttribBook | null;
  rollNum: string;
  setRollNum: (v: string) => void;
  rollWindow: number;
  setRollWindow: (v: number) => void;
}) {
  const data = rolling?.series ?? [];
  return (
    <section className="mt-4 overflow-hidden rounded border border-zinc-800 bg-zinc-950">
      <div className="flex flex-wrap items-center gap-2 border-b border-zinc-800 bg-zinc-900/60 px-4 py-2.5">
        <h2 className="text-sm font-semibold">Rolling α / β</h2>
        <span className="text-[10px] uppercase tracking-widest text-zinc-600">
          fällt β im Crash? erodiert α?
        </span>
        <div className="ml-auto flex items-center gap-2">
          <select
            value={rollNum}
            onChange={(e) => setRollNum(e.target.value)}
            className="rounded border border-zinc-700 bg-zinc-900 px-2 py-1 text-xs text-zinc-100"
          >
            <option value="PORTFOLIO">Portfolio (Equal Weight)</option>
            {(book?.strategies ?? []).map((s) => (
              <option key={s.num} value={s.num}>{s.label}</option>
            ))}
          </select>
          <div className="flex overflow-hidden rounded border border-zinc-700">
            {[
              { d: 63, l: "63T" },
              { d: 126, l: "126T" },
              { d: 252, l: "252T" },
            ].map((w) => (
              <button
                key={w.d}
                onClick={() => setRollWindow(w.d)}
                className={cls("px-2 py-1 text-xs", rollWindow === w.d ? "bg-zinc-700 text-zinc-100" : "bg-zinc-900 text-zinc-400 hover:bg-zinc-800")}
              >
                {w.l}
              </button>
            ))}
          </div>
        </div>
      </div>
      <div className="px-2 pb-3 pt-2">
        {data.length === 0 ? (
          <Empty />
        ) : (
          <ResponsiveContainer width="100%" height={300}>
            <ComposedChart data={data} margin={{ top: 8, right: 50, bottom: 4, left: 0 }}>
              <CartesianGrid stroke="#27272a" strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey="t" tick={{ fill: "#71717a", fontSize: 10 }} minTickGap={60} axisLine={false} tickLine={false} />
              {/* left axis: beta + benchmark drawdown */}
              <YAxis yAxisId="L" tick={{ fill: "#71717a", fontSize: 10 }} axisLine={false} tickLine={false} domain={["auto", "auto"]} />
              {/* right axis: alpha */}
              <YAxis yAxisId="R" orientation="right" tickFormatter={(v) => `${(v * 100).toFixed(0)}%`} tick={{ fill: "#71717a", fontSize: 10 }} axisLine={false} tickLine={false} />
              <ReferenceLine yAxisId="L" y={0} stroke="#3f3f46" />
              <ReferenceLine yAxisId="L" y={1} stroke="#3f3f46" strokeDasharray="2 2" />
              <Tooltip
                contentStyle={{ background: "#18181b", border: "1px solid #3f3f46", borderRadius: 6, fontSize: 12 }}
                labelStyle={{ color: "#a1a1aa" }}
                formatter={(v, n) => {
                  const num = Number(v);
                  if (n === "Benchmark DD" || n === "α p.a.") return [`${(num * 100).toFixed(1)}%`, n];
                  return [num.toFixed(3), n];
                }}
              />
              {/* benchmark drawdown shaded to mark crashes */}
              <Area yAxisId="L" type="monotone" dataKey="bench_dd" name="Benchmark DD" stroke="#52525b" fill="#ef4444" fillOpacity={0.12} isAnimationActive={false} />
              <Line yAxisId="L" type="monotone" dataKey="beta" name="β" stroke="#38bdf8" strokeWidth={1.8} dot={false} isAnimationActive={false} />
              <Line yAxisId="R" type="monotone" dataKey="alpha" name="α p.a." stroke="#22c55e" strokeWidth={1.8} dot={false} isAnimationActive={false} />
            </ComposedChart>
          </ResponsiveContainer>
        )}
        <div className="flex flex-wrap gap-x-4 px-3 pt-1 text-[10px] text-zinc-500">
          <span className="inline-flex items-center gap-1.5"><span className="h-2 w-2 rounded-full bg-sky-400" /> β (links)</span>
          <span className="inline-flex items-center gap-1.5"><span className="h-2 w-2 rounded-full bg-emerald-400" /> α p.a. (rechts)</span>
          <span className="inline-flex items-center gap-1.5"><span className="h-2 w-3 rounded-sm bg-red-500/30" /> Benchmark-Drawdown</span>
        </div>
      </div>
    </section>
  );
}

// ── brinson sector table ────────────────────────────────────────────────────────
function BrinsonTable({ brinson }: { brinson: AttribBrinson | null }) {
  const rows = brinson?.sectors ?? [];
  return (
    <section className="mt-4 overflow-hidden rounded border border-zinc-800">
      <PanelHead title="Sektor-Attribution" sub="Allokation · Selektion · Interaktion je Sektor" border={false} />
      <div className="overflow-x-auto">
        <table className="w-full text-right text-xs">
          <thead className="bg-zinc-900/40 text-[10px] uppercase tracking-wide text-zinc-500">
            <tr>
              <th className="px-4 py-2 text-left">Sektor</th>
              <th className="px-3 py-2 text-left">Benchmark</th>
              <th className="px-3 py-2">w_p</th>
              <th className="px-3 py-2">r_p</th>
              <th className="px-3 py-2">r_b</th>
              <th className="px-3 py-2">Allokation</th>
              <th className="px-3 py-2">Selektion</th>
              <th className="px-3 py-2">Interaktion</th>
              <th className="px-3 py-2">Total</th>
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 && (
              <tr><td colSpan={9} className="px-4 py-8 text-center text-zinc-600">keine Daten</td></tr>
            )}
            {rows.map((s) => (
              <tr key={s.sector} className="border-b border-zinc-900 hover:bg-zinc-900/50">
                <td className="px-4 py-2 text-left font-medium text-zinc-100">{s.label}<span className="ml-1.5 text-[10px] text-zinc-600">{s.n_sleeves} Sl.</span></td>
                <td className="px-3 py-2 text-left font-mono text-zinc-500">{s.benchmark}</td>
                <td className="px-3 py-2 font-mono tabular-nums text-zinc-400">{(s.w_p * 100).toFixed(0)}%</td>
                <td className={cls("px-3 py-2 font-mono tabular-nums", s.r_p >= 0 ? "text-emerald-300/90" : "text-red-300/90")}>{pct(s.r_p, 1)}</td>
                <td className={cls("px-3 py-2 font-mono tabular-nums", s.r_b >= 0 ? "text-emerald-300/90" : "text-red-300/90")}>{pct(s.r_b, 1)}</td>
                <Effect v={s.allocation} />
                <Effect v={s.selection} />
                <Effect v={s.interaction} />
                <td className={cls("px-3 py-2 font-mono tabular-nums font-semibold", s.total >= 0 ? "text-emerald-300" : "text-red-300")}>{pct(s.total, 2)}</td>
              </tr>
            ))}
          </tbody>
          {brinson && (
            <tfoot className="border-t border-zinc-700 bg-zinc-900/40 font-mono text-zinc-200">
              <tr>
                <td className="px-4 py-2 text-left font-semibold" colSpan={5}>Total (Active Return {pct(brinson.active_return)})</td>
                <td className={cls("px-3 py-2 text-right tabular-nums", brinson.allocation_total >= 0 ? "text-emerald-300" : "text-red-300")}>{pct(brinson.allocation_total)}</td>
                <td className={cls("px-3 py-2 text-right tabular-nums", brinson.selection_total >= 0 ? "text-emerald-300" : "text-red-300")}>{pct(brinson.selection_total)}</td>
                <td className={cls("px-3 py-2 text-right tabular-nums", brinson.interaction_total >= 0 ? "text-emerald-300" : "text-red-300")}>{pct(brinson.interaction_total)}</td>
                <td className={cls("px-3 py-2 text-right tabular-nums font-bold", brinson.active_return >= 0 ? "text-emerald-300" : "text-red-300")}>{pct(brinson.active_return)}</td>
              </tr>
            </tfoot>
          )}
        </table>
      </div>
    </section>
  );
}

function Effect({ v }: { v: number }) {
  return (
    <td className={cls("px-3 py-2 font-mono tabular-nums", v >= 0 ? "text-emerald-300/80" : "text-red-300/80")}>
      {pct(v, 2)}
    </td>
  );
}

// ── shared bits ──────────────────────────────────────────────────────────────
function PanelHead({ title, sub, border = true }: { title: string; sub?: string; border?: boolean }) {
  return (
    <div className={cls("flex items-center gap-2 px-4 py-2.5", border && "border-b border-zinc-800 bg-zinc-900/60")}>
      <h2 className="text-sm font-semibold">{title}</h2>
      {sub && <span className="text-[10px] uppercase tracking-widest text-zinc-600">{sub}</span>}
    </div>
  );
}

function Empty() {
  return <div className="py-16 text-center text-xs text-zinc-600">keine Daten</div>;
}
