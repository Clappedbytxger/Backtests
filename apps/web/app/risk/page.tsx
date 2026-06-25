"use client";

import { useCallback, useEffect, useState } from "react";
import {
  getRiskBook,
  getRiskCorrelation,
  getRiskDashboard,
  type RiskBook,
  type RiskCorrelationSeries,
  type RiskDashboard,
  type RiskWarnLevel,
} from "@/lib/api";
import RiskHeatmap from "./RiskHeatmap";
import AllocationChart from "./AllocationChart";
import RollingCorr from "./RollingCorr";

const cls = (...x: (string | false | undefined)[]) => x.filter(Boolean).join(" ");
const pct = (v: number | null | undefined, d = 1) =>
  v == null || !isFinite(v) ? "—" : `${(v * 100).toFixed(d)}%`;
const num = (v: number | null | undefined, d = 2) =>
  v == null || !isFinite(v) ? "—" : v.toFixed(d);
const eur = (v: number | null | undefined) =>
  v == null || !isFinite(v) ? "—" : `€${Math.round(v).toLocaleString("de-DE")}`;

const WARN: Record<RiskWarnLevel, { ring: string; text: string; dot: string; label: string }> = {
  green: { ring: "border-emerald-700/60", text: "text-emerald-300", dot: "bg-emerald-400", label: "NORMAL" },
  yellow: { ring: "border-amber-600/70", text: "text-amber-300", dot: "bg-amber-400", label: "ERHÖHT" },
  red: { ring: "border-red-600 shadow-[0_0_24px_-6px_rgba(239,68,68,0.6)]", text: "text-red-300", dot: "bg-red-500", label: "VaR-LIMIT" },
  unknown: { ring: "border-zinc-700", text: "text-zinc-400", dot: "bg-zinc-500", label: "—" },
};

export default function RiskPage() {
  const [book, setBook] = useState<RiskBook | null>(null);
  const [data, setData] = useState<RiskDashboard | null>(null);
  const [sel, setSel] = useState<string[]>([]);
  const [window, setWindow] = useState("full");
  const [weighting, setWeighting] = useState("equal_weight");
  const [capital, setCapital] = useState(100_000);
  const [varLimit, setVarLimit] = useState(0.02);
  const [pair, setPair] = useState<{ a: string; b: string } | null>(null);
  const [roll, setRoll] = useState<RiskCorrelationSeries | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getRiskBook()
      .then((b) => {
        setBook(b);
        if (b.ok) setSel(b.default_selection);
      })
      .catch((e) => setError(String(e)));
  }, []);

  const refresh = useCallback(() => {
    if (!sel.length) return;
    setLoading(true);
    getRiskDashboard({ window, nums: sel, capital, weighting, varLimitPct: varLimit })
      .then((d) => {
        if (!d.ok) setError(d.error || "Risk-Engine-Fehler");
        else {
          setData(d);
          setError(null);
        }
      })
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false));
  }, [sel, window, capital, weighting, varLimit]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const selectPair = useCallback((a: string, b: string) => {
    if (a === b) return;
    setPair({ a, b });
    getRiskCorrelation(a, b, 90).then(setRoll).catch(() => setRoll(null));
  }, []);

  const toggle = (n: string) =>
    setSel((s) => (s.includes(n) ? s.filter((x) => x !== n) : [...s, n]));

  if (error && !data)
    return (
      <main className="mx-auto max-w-7xl p-8">
        <div className="rounded-lg border border-red-900 bg-red-950/40 p-4 text-sm text-red-300">
          Risk-API nicht erreichbar ({error}). Starte sie mit{" "}
          <code>uvicorn apps.api.main:app --port 8000</code>.
        </div>
      </main>
    );

  const p = data?.summary.portfolio;
  const cells = p?.var_es;
  const w = data ? WARN[data.warn_level] : WARN.unknown;
  const cur95 = p?.var_currency?.["95_1d"];
  const es95cur = p?.es_currency?.["95_1d"];

  return (
    <main className="mx-auto max-w-7xl px-6 py-6">
      {/* header */}
      <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-lg font-semibold tracking-tight text-zinc-100">
            Risk Desk <span className="text-zinc-500">· Institutional Risk Management</span>
          </h1>
          <p className="mt-0.5 text-xs text-zinc-500">
            VaR · Expected Shortfall · Korrelationsstruktur · Kapitalallokation (MVO / HRP) über das aktive Strategie-Buch.
            {data && (
              <>
                {" "}
                <span className="text-zinc-400">
                  {data.summary.n_strategies} Sleeves · {data.n_obs} Handelstage ·{" "}
                  {data.span.start}–{data.span.end}
                </span>
              </>
            )}
          </p>
        </div>
        <div
          className={cls(
            "flex items-center gap-2 rounded-lg border bg-zinc-900/60 px-3 py-1.5 text-xs",
            w.ring,
          )}
        >
          <span className={cls("h-2.5 w-2.5 animate-pulse rounded-full", w.dot)} />
          <span className={cls("font-semibold tracking-wide", w.text)}>{w.label}</span>
          {loading && <span className="text-zinc-500">…</span>}
        </div>
      </div>

      {/* controls */}
      <div className="mb-5 flex flex-wrap items-center gap-2 rounded-lg border border-zinc-800 bg-zinc-900/40 p-2.5 text-xs">
        <Seg
          label="Fenster"
          value={window}
          onChange={setWindow}
          options={(book?.windows ?? []).map((x) => ({ key: x.key, label: x.label }))}
        />
        <div className="h-5 w-px bg-zinc-800" />
        <Seg
          label="Gewichtung"
          value={weighting}
          onChange={setWeighting}
          options={(book?.weightings ?? []).map((x) => ({ key: x.key, label: x.label }))}
        />
        <div className="h-5 w-px bg-zinc-800" />
        <label className="flex items-center gap-1.5 text-zinc-400">
          Kapital
          <input
            type="number"
            value={capital}
            step={10000}
            onChange={(e) => setCapital(Math.max(1, +e.target.value))}
            className="w-24 rounded border border-zinc-700 bg-zinc-950 px-1.5 py-1 font-mono text-zinc-200"
          />
        </label>
        <label className="flex items-center gap-1.5 text-zinc-400">
          VaR-Limit
          <input
            type="number"
            value={varLimit * 100}
            step={0.5}
            min={0.1}
            onChange={(e) => setVarLimit(Math.max(0.001, +e.target.value / 100))}
            className="w-16 rounded border border-zinc-700 bg-zinc-950 px-1.5 py-1 font-mono text-zinc-200"
          />
          <span className="text-zinc-600">%/Tag</span>
        </label>
      </div>

      {/* summary cards */}
      <div className="mb-5 grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Card
          title="Value-at-Risk · 95% · 1 Tag"
          big={pct(cells?.["95_1d"].var_historical, 2)}
          sub={`${eur(cur95)} · hist. · param. ${pct(cells?.["95_1d"].var_parametric, 2)}`}
          tone={w}
        />
        <Card
          title="Expected Shortfall · 95% · 1T"
          big={pct(cells?.["95_1d"].es_historical, 2)}
          sub={`${eur(es95cur)} · Ø Verlust jenseits VaR`}
          tone={WARN.unknown}
        />
        <Card
          title="Diversifikations-Benefit"
          big={pct(p?.diversification.benefit, 0)}
          sub={`Diversification Ratio ${num(p?.diversification.diversification_ratio)}`}
          tone={
            (p?.diversification.benefit ?? 0) > 0.3
              ? WARN.green
              : (p?.diversification.benefit ?? 0) > 0.1
                ? WARN.yellow
                : WARN.red
          }
          accent="cyan"
        />
        <Card
          title="Portfolio · annualisiert"
          big={`Sharpe ${num(p?.sharpe)}`}
          sub={`Vol ${pct(p?.vol_annual)} · Return ${pct(p?.return_annual)}`}
          tone={WARN.unknown}
          accent="zinc"
        />
      </div>

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
        {/* VaR / ES grid */}
        <section className="rounded-lg border border-zinc-800 bg-zinc-900/40 p-4">
          <h2 className="mb-3 text-sm font-medium text-zinc-200">
            VaR / Expected Shortfall — Konfidenz × Horizont
          </h2>
          <table className="w-full text-xs">
            <thead>
              <tr className="text-zinc-500">
                <th className="pb-2 text-left font-normal">Szenario</th>
                <th className="pb-2 text-right font-normal">VaR hist.</th>
                <th className="pb-2 text-right font-normal">VaR param.</th>
                <th className="pb-2 text-right font-normal">ES hist.</th>
                <th className="pb-2 text-right font-normal">in €</th>
              </tr>
            </thead>
            <tbody className="font-mono">
              {["95_1d", "99_1d", "95_10d", "99_10d"].map((k) => {
                const c = cells?.[k];
                const label = k.replace("_", "% · ").replace("d", " Tage");
                return (
                  <tr key={k} className="border-t border-zinc-800/70">
                    <td className="py-1.5 font-sans text-zinc-400">{label}</td>
                    <td className="py-1.5 text-right text-zinc-100">{pct(c?.var_historical, 2)}</td>
                    <td className="py-1.5 text-right text-zinc-400">{pct(c?.var_parametric, 2)}</td>
                    <td className="py-1.5 text-right text-amber-300/90">{pct(c?.es_historical, 2)}</td>
                    <td className="py-1.5 text-right text-zinc-300">
                      {eur(p?.var_currency?.[k])}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          <p className="mt-2 text-[10px] text-zinc-600">
            Historisch = empirisches Quantil der realisierten Renditen · Parametrisch =
            Varianz-Kovarianz (Gauß) · 10-Tage über √t skaliert.
          </p>
        </section>

        {/* correlation heatmap */}
        <section className="rounded-lg border border-zinc-800 bg-zinc-900/40 p-4">
          <h2 className="mb-3 text-sm font-medium text-zinc-200">
            Dynamische Korrelationsmatrix
          </h2>
          {data && (
            <RiskHeatmap
              labels={data.correlation.labels}
              matrix={data.correlation.matrix}
              onSelect={selectPair}
              selected={pair}
            />
          )}
        </section>
      </div>

      {/* rolling correlation drilldown */}
      {roll && roll.ok && (
        <div className="mt-5">
          <RollingCorr data={roll} />
        </div>
      )}

      {/* allocation vs risk contribution */}
      <section className="mt-5 rounded-lg border border-zinc-800 bg-zinc-900/40 p-4">
        <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
          <h2 className="text-sm font-medium text-zinc-200">
            Allokation vs. Risiko-Beitrag{" "}
            <span className="text-zinc-500">· {data?.weighting_label}</span>
          </h2>
          <div className="text-[10px] text-zinc-500">
            <span className="mr-3">
              <span className="mr-1 inline-block h-2 w-2 rounded-sm bg-cyan-400" />
              Kapital-Allokation
            </span>
            <span>
              <span className="mr-1 inline-block h-2 w-2 rounded-sm bg-red-500" />
              Risiko-Beitrag (rot = überproportional)
            </span>
          </div>
        </div>
        {data && <AllocationChart alloc={data.allocations[data.weighting]} />}
        {data && (
          <div className="mt-2 grid grid-cols-2 gap-2 text-[11px] text-zinc-500 sm:grid-cols-4">
            {Object.values(data.allocations).map((a) => (
              <button
                key={a.method}
                onClick={() => setWeighting(a.method)}
                className={cls(
                  "rounded border px-2 py-1 text-left transition",
                  data.weighting === a.method
                    ? "border-zinc-500 bg-zinc-800/60 text-zinc-200"
                    : "border-zinc-800 hover:border-zinc-600",
                )}
              >
                <div className="font-medium">{a.method.replace("mvo_", "").replace("_", " ")}</div>
                <div className="font-mono text-[10px] text-zinc-500">
                  Sharpe {num(a.sharpe)} · Vol {pct(a.vol)}
                </div>
              </button>
            ))}
          </div>
        )}
      </section>

      {/* per-strategy risk table */}
      <section className="mt-5 rounded-lg border border-zinc-800 bg-zinc-900/40 p-4">
        <h2 className="mb-3 text-sm font-medium text-zinc-200">Strategien im Buch</h2>
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="text-zinc-500">
                <th className="pb-2 text-left font-normal">#</th>
                <th className="pb-2 text-left font-normal">Strategie</th>
                <th className="pb-2 text-left font-normal">Status</th>
                <th className="pb-2 text-right font-normal">Allok.</th>
                <th className="pb-2 text-right font-normal">Risk%</th>
                <th className="pb-2 text-right font-normal">Vol p.a.</th>
                <th className="pb-2 text-right font-normal">Sharpe</th>
                <th className="pb-2 text-right font-normal">Ret p.a.</th>
                <th className="pb-2 text-center font-normal">im Buch</th>
              </tr>
            </thead>
            <tbody className="font-mono">
              {data?.summary.per_strategy.map((s) => {
                const meta = data.strategies.find((m) => m.label === s.strategy);
                const num4 = s.strategy.slice(0, 4);
                const over = (s.risk_pct ?? 0) > (s.weight ?? 0) + 0.01;
                // standalone risk from the sleeve's OWN life (honest; not diluted by 0-fill)
                const volA = meta?.vol_annual ?? s.vol_annual;
                const sharpe =
                  meta && meta.vol_annual && meta.return_annual != null
                    ? meta.return_annual / meta.vol_annual
                    : s.sharpe;
                return (
                  <tr key={s.strategy} className="border-t border-zinc-800/70">
                    <td className="py-1.5 text-zinc-500">{num4}</td>
                    <td className="py-1.5 font-sans text-zinc-200">{meta?.name ?? s.strategy.slice(5)}</td>
                    <td className="py-1.5 font-sans text-[10px] text-zinc-500">{meta?.status ?? "—"}</td>
                    <td className="py-1.5 text-right text-cyan-300">{pct(s.weight)}</td>
                    <td className={cls("py-1.5 text-right", over ? "text-red-300" : "text-zinc-300")}>
                      {pct(s.risk_pct)}
                    </td>
                    <td className="py-1.5 text-right text-zinc-300">{pct(volA)}</td>
                    <td className="py-1.5 text-right text-zinc-300">{num(sharpe)}</td>
                    <td className="py-1.5 text-right text-zinc-400">{pct(meta?.return_annual)}</td>
                    <td className="py-1.5 text-center">
                      <input
                        type="checkbox"
                        checked={sel.includes(num4)}
                        onChange={() => toggle(num4)}
                        className="accent-cyan-500"
                      />
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        <p className="mt-2 text-[10px] text-zinc-600">
          Vol/Sharpe/Return p.a. = Standalone über die Lebensspanne des Sleeves (inkl. Flat-Tage).
          Allokation &amp; Risk% sind Buch-Level (Euler-Zerlegung): <span className="text-red-300">Risk% &gt; Allok.</span> =
          überproportionaler Risikobeitrag. Sleeves ohne Position gelten als flat (0), nicht als fehlend.
        </p>
        {book && sel.length < book.count && (
          <button
            onClick={() => setSel(book.default_selection)}
            className="mt-3 rounded border border-zinc-700 px-2 py-1 text-[11px] text-zinc-400 hover:border-zinc-500"
          >
            Alle {book.count} Strategien wieder aufnehmen
          </button>
        )}
      </section>
    </main>
  );
}

// ── small presentational helpers ──────────────────────────────────────────────

function Card({
  title,
  big,
  sub,
  tone,
  accent = "default",
}: {
  title: string;
  big: string;
  sub: string;
  tone: { ring: string; text: string };
  accent?: "default" | "cyan" | "zinc";
}) {
  const bigColor =
    accent === "cyan" ? "text-cyan-300" : accent === "zinc" ? "text-zinc-100" : tone.text;
  return (
    <div className={cls("rounded-lg border bg-zinc-900/50 p-3.5", tone.ring)}>
      <div className="text-[10px] uppercase tracking-wide text-zinc-500">{title}</div>
      <div className={cls("mt-1 text-2xl font-semibold tabular-nums", bigColor)}>{big}</div>
      <div className="mt-1 text-[11px] text-zinc-500">{sub}</div>
    </div>
  );
}

function Seg<T extends string>({
  label,
  value,
  onChange,
  options,
}: {
  label: string;
  value: T;
  onChange: (v: T) => void;
  options: { key: T; label: string }[];
}) {
  return (
    <div className="flex items-center gap-1.5">
      <span className="text-zinc-500">{label}</span>
      <div className="flex overflow-hidden rounded border border-zinc-700">
        {options.map((o) => (
          <button
            key={o.key}
            onClick={() => onChange(o.key)}
            className={cls(
              "px-2 py-1 transition",
              value === o.key
                ? "bg-zinc-700 text-zinc-100"
                : "bg-zinc-950 text-zinc-400 hover:bg-zinc-800",
            )}
          >
            {o.label}
          </button>
        ))}
      </div>
    </div>
  );
}
