"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  getOptimizeConfig,
  getOptimizeJob,
  startOptimize,
  type OptConfig,
  type OptJob,
  type OptStrategy,
  type OptTopRow,
} from "@/lib/api";
import SurfacePlot from "./SurfacePlot";

const num = (x: number | null | undefined, d = 2) =>
  typeof x === "number" && Number.isFinite(x) ? x.toFixed(d) : "—";
const pct = (x: number | null | undefined, d = 1) =>
  typeof x === "number" && Number.isFinite(x) ? `${(x * 100).toFixed(d)}%` : "—";

export default function OptimizePage() {
  const [cfg, setCfg] = useState<OptConfig | null>(null);
  const [err, setErr] = useState<string | null>(null);

  // form state
  const [ticker, setTicker] = useState("SPY");
  const [strategyKey, setStrategyKey] = useState("ma_crossover");
  const [fitness, setFitness] = useState("sharpe_dd");
  const [popSize, setPopSize] = useState(40);
  const [generations, setGenerations] = useState(30);
  const [selection, setSelection] = useState("tournament");
  const [crossover, setCrossover] = useState(0.9);
  const [baseMut, setBaseMut] = useState(0.3);
  const [minMut, setMinMut] = useState(0.05);
  const [elitism, setElitism] = useState(2);
  const [oosFrac, setOosFrac] = useState(0.3);
  const [haircut, setHaircut] = useState(50);
  const [seed, setSeed] = useState(42);

  // run state
  const [job, setJob] = useState<OptJob | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    getOptimizeConfig()
      .then(setCfg)
      .catch((e) => setErr(String(e)));
  }, []);

  const stopPolling = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, []);

  useEffect(() => stopPolling, [stopPolling]);

  const strategy: OptStrategy | undefined = cfg?.strategies.find((s) => s.key === strategyKey);

  const launch = async () => {
    setErr(null);
    try {
      const { job_id } = await startOptimize({
        ticker,
        strategy: strategyKey,
        fitness_metric: fitness,
        population_size: popSize,
        generations,
        selection,
        crossover_prob: crossover,
        base_mutation_rate: baseMut,
        min_mutation_rate: minMut,
        elitism,
        oos_fraction: oosFrac,
        haircut_reject_pct: haircut,
        seed,
      });
      setJob({
        ok: true,
        job_id,
        status: "running",
        ticker,
        strategy: strategyKey,
        fitness_metric: fitness,
        generations,
        current_generation: -1,
        progress: 0,
        history: [],
      });
      stopPolling();
      pollRef.current = setInterval(async () => {
        try {
          const j = await getOptimizeJob(job_id);
          setJob(j);
          if (j.status !== "running") stopPolling();
        } catch {
          /* transient */
        }
      }, 700);
    } catch (e) {
      setErr(String(e));
    }
  };

  if (err && !cfg)
    return (
      <main className="mx-auto max-w-6xl p-8">
        <div className="rounded-lg border border-red-900 bg-red-950/40 p-4 text-sm text-red-300">
          API nicht erreichbar ({err}). Starte sie mit <code>uvicorn apps.api.main:app</code>.
        </div>
      </main>
    );

  const running = job?.status === "running";
  const result = job?.status === "done" ? job.result : undefined;
  const history = job?.history ?? [];
  const chartData = history.map((g) => ({
    gen: g.generation,
    best: g.best_fitness,
    avg: g.avg_fitness,
    mut: g.mutation_rate,
    div: g.diversity,
  }));

  return (
    <main className="mx-auto max-w-7xl p-8">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-semibold tracking-tight">Evolution Monitor</h1>
          <p className="mt-1 text-sm text-zinc-400">
            Genetischer Algorithmus · robuste Parameter statt langsamer Grid-Search · IS/OOS-Schutz
          </p>
        </div>
        <span
          className={`flex items-center gap-2 rounded-full border px-3 py-1 text-xs ${
            running ? "border-emerald-600 text-emerald-300" : "border-zinc-700 text-zinc-400"
          }`}
        >
          <span className={`h-2 w-2 rounded-full ${running ? "animate-pulse bg-emerald-400" : "bg-zinc-500"}`} />
          {running ? `Generation ${job!.current_generation + 1}/${job!.generations}` : job?.status === "done" ? "fertig" : "bereit"}
        </span>
      </div>

      <div className="mt-8 grid gap-8 lg:grid-cols-[300px_1fr]">
        {/* ── control panel ──────────────────────────────────────────── */}
        <aside className="space-y-4">
          <Panel title="Setup">
            <Field label="Instrument">
              <select value={ticker} onChange={(e) => setTicker(e.target.value)} className={inputCls}>
                {cfg?.instruments.map((i) => (
                  <option key={i.ticker} value={i.ticker}>
                    {i.ticker} — {i.name}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Strategie">
              <select value={strategyKey} onChange={(e) => setStrategyKey(e.target.value)} className={inputCls}>
                {cfg?.strategies.map((s) => (
                  <option key={s.key} value={s.key}>
                    {s.label}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Fitness-Funktion">
              <select value={fitness} onChange={(e) => setFitness(e.target.value)} className={inputCls}>
                {cfg?.fitness_functions.map((f) => (
                  <option key={f.key} value={f.key}>
                    {f.label}
                  </option>
                ))}
              </select>
            </Field>
          </Panel>

          <Panel title="GA-Parameter">
            <NumField label="Population" value={popSize} set={setPopSize} min={8} max={200} step={1} />
            <NumField label="Generationen" value={generations} set={setGenerations} min={3} max={120} step={1} />
            <Field label="Selektion">
              <select value={selection} onChange={(e) => setSelection(e.target.value)} className={inputCls}>
                <option value="tournament">Tournament</option>
                <option value="roulette">Roulette-Wheel</option>
              </select>
            </Field>
            <NumField label="Crossover-Rate" value={crossover} set={setCrossover} min={0} max={1} step={0.05} />
            <NumField label="Mutation (Start)" value={baseMut} set={setBaseMut} min={0} max={1} step={0.05} />
            <NumField label="Mutation (Min)" value={minMut} set={setMinMut} min={0} max={0.5} step={0.01} />
            <NumField label="Elitismus" value={elitism} set={setElitism} min={0} max={20} step={1} />
            <NumField label="Seed" value={seed} set={setSeed} min={0} max={9999} step={1} />
          </Panel>

          <Panel title="Overfitting-Schutz">
            <NumField label="OOS-Anteil" value={oosFrac} set={setOosFrac} min={0.1} max={0.5} step={0.05} />
            <NumField label="Haircut-Limit %" value={haircut} set={setHaircut} min={10} max={90} step={5} />
            <p className="text-[11px] leading-relaxed text-zinc-500">
              Fitness wird nur in-sample optimiert, dann out-of-sample validiert. Ein IS→OOS-Abfall &gt;{" "}
              {haircut}% markiert den Parametersatz als überoptimiert.
            </p>
          </Panel>

          <button
            onClick={launch}
            disabled={running}
            className="w-full rounded-lg bg-emerald-600 px-4 py-2.5 text-sm font-medium text-white transition hover:bg-emerald-500 disabled:opacity-40"
          >
            {running ? "Evolution läuft…" : "Optimierung starten"}
          </button>
          {err && <p className="text-xs text-red-400">{err}</p>}
        </aside>

        {/* ── monitor ────────────────────────────────────────────────── */}
        <section className="space-y-6">
          {/* progress */}
          {job && (
            <div className="h-1.5 w-full overflow-hidden rounded-full bg-zinc-800">
              <div
                className="h-full rounded-full bg-emerald-500 transition-all duration-300"
                style={{ width: `${Math.round((job.progress ?? 0) * 100)}%` }}
              />
            </div>
          )}

          {/* convergence chart */}
          <Card title="Konvergenz" subtitle="Beste vs. durchschnittliche Fitness je Generation · Mutationsrate (rechts)">
            {chartData.length === 0 ? (
              <Placeholder text="Starte eine Optimierung — die Konvergenz erscheint hier live." />
            ) : (
              <ResponsiveContainer width="100%" height={300}>
                <LineChart data={chartData} margin={{ top: 8, right: 12, left: -8, bottom: 4 }}>
                  <CartesianGrid stroke="#27272a" strokeDasharray="3 3" />
                  <XAxis dataKey="gen" stroke="#71717a" fontSize={11} label={{ value: "Generation", position: "insideBottom", offset: -2, fill: "#71717a", fontSize: 11 }} />
                  <YAxis yAxisId="fit" stroke="#71717a" fontSize={11} />
                  <YAxis yAxisId="mut" orientation="right" stroke="#52525b" fontSize={11} domain={[0, 1]} />
                  <Tooltip
                    contentStyle={{ background: "#18181b", border: "1px solid #3f3f46", borderRadius: 8, fontSize: 12 }}
                    labelStyle={{ color: "#a1a1aa" }}
                    formatter={(v, n) => [typeof v === "number" ? v.toFixed(4) : String(v), n]}
                  />
                  <Legend wrapperStyle={{ fontSize: 11 }} />
                  <Line yAxisId="fit" type="monotone" dataKey="best" name="Beste Fitness" stroke="#34d399" strokeWidth={2} dot={false} isAnimationActive={false} />
                  <Line yAxisId="fit" type="monotone" dataKey="avg" name="Ø Fitness" stroke="#60a5fa" strokeWidth={1.5} dot={false} isAnimationActive={false} />
                  <Line yAxisId="mut" type="monotone" dataKey="mut" name="Mutationsrate" stroke="#f59e0b" strokeWidth={1} strokeDasharray="4 3" dot={false} isAnimationActive={false} />
                </LineChart>
              </ResponsiveContainer>
            )}
          </Card>

          {/* surface */}
          <Card
            title="Parameter-Surface"
            subtitle={
              result?.surface
                ? "Fitness-Oberfläche der zwei Leitparameter — breites Plateau = robust, scharfe Spitze = überoptimiert"
                : "Erscheint nach Abschluss der Optimierung"
            }
          >
            {result?.surface ? (
              <SurfacePlot surface={result.surface} />
            ) : (
              <Placeholder text="Die Oberfläche wird am Ende des Laufs aus dem In-Sample-Gitter berechnet." />
            )}
          </Card>

          {/* result matrix */}
          {result && (
            <Card
              title="Resultat-Matrix"
              subtitle={`Top ${result.top.length} Parametersätze · ${result.span.start} – ${result.span.end} (${result.span.bars} Bars) · Kostenmodell: ${result.cost_model}`}
            >
              <ResultMatrix top={result.top} paramNames={result.param_names} haircutLimit={result.haircut_reject_pct} />
            </Card>
          )}

          {job?.status === "error" && (
            <div className="rounded-lg border border-red-900 bg-red-950/40 p-4 text-sm text-red-300">
              Fehler: {job.error}
            </div>
          )}
        </section>
      </div>
    </main>
  );
}

function ResultMatrix({
  top,
  paramNames,
  haircutLimit,
}: {
  top: OptTopRow[];
  paramNames: string[];
  haircutLimit: number;
}) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse text-sm">
        <thead>
          <tr className="border-b border-zinc-800 text-left text-xs uppercase tracking-wide text-zinc-500">
            <th className="py-2 pr-3">#</th>
            {paramNames.map((p) => (
              <th key={p} className="py-2 pr-3 font-mono normal-case">
                {p}
              </th>
            ))}
            <th className="py-2 pr-3">IS Sharpe</th>
            <th className="py-2 pr-3">OOS Sharpe</th>
            <th className="py-2 pr-3">IS CAGR</th>
            <th className="py-2 pr-3">OOS CAGR</th>
            <th className="py-2 pr-3">OOS MaxDD</th>
            <th className="py-2 pr-3">Haircut</th>
            <th className="py-2 pr-3">Status</th>
          </tr>
        </thead>
        <tbody>
          {top.map((r, i) => (
            <tr key={i} className="border-b border-zinc-900 hover:bg-zinc-900/40">
              <td className="py-2 pr-3 text-zinc-500">{i + 1}</td>
              {paramNames.map((p) => (
                <td key={p} className="py-2 pr-3 font-mono text-zinc-200">
                  {Number.isInteger(r.params[p]) ? r.params[p] : r.params[p]?.toFixed(3)}
                </td>
              ))}
              <td className="py-2 pr-3 text-zinc-300">{num(r.is.sharpe)}</td>
              <td className={`py-2 pr-3 ${(r.oos.sharpe ?? 0) >= (r.is.sharpe ?? 0) * 0.5 ? "text-emerald-300" : "text-amber-300"}`}>
                {num(r.oos.sharpe)}
              </td>
              <td className="py-2 pr-3 text-zinc-400">{pct(r.is.cagr)}</td>
              <td className="py-2 pr-3 text-zinc-400">{pct(r.oos.cagr)}</td>
              <td className="py-2 pr-3 text-zinc-400">{pct(r.oos.max_drawdown)}</td>
              <td className="py-2 pr-3 text-zinc-300">{r.haircut_pct == null ? "—" : `${r.haircut_pct.toFixed(0)}%`}</td>
              <td className="py-2 pr-3">
                {r.overfit ? (
                  <span className="rounded-full border border-amber-700 bg-amber-950/40 px-2 py-0.5 text-[11px] text-amber-300">
                    überoptimiert
                  </span>
                ) : (
                  <span className="rounded-full border border-emerald-800 bg-emerald-950/30 px-2 py-0.5 text-[11px] text-emerald-300">
                    stabil
                  </span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="mt-3 text-[11px] text-zinc-500">
        „überoptimiert" = IS→OOS-Fitness-Abfall &gt; {haircutLimit}%. Eine OOS-Sharpe nahe der IS-Sharpe
        ist das eigentliche Qualitätssignal, nicht die höchste IS-Fitness.
      </p>
    </div>
  );
}

// ── small UI primitives ─────────────────────────────────────────────────────
const inputCls =
  "w-full rounded-md border border-zinc-700 bg-zinc-900 px-2.5 py-1.5 text-sm text-zinc-100 focus:border-emerald-600 focus:outline-none";

function Panel({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-xl border border-zinc-800 bg-zinc-900/40 p-4">
      <div className="mb-3 text-xs font-semibold uppercase tracking-widest text-zinc-500">{title}</div>
      <div className="space-y-3">{children}</div>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block text-xs text-zinc-400">
      <span className="mb-1 block">{label}</span>
      {children}
    </label>
  );
}

function NumField({
  label,
  value,
  set,
  min,
  max,
  step,
}: {
  label: string;
  value: number;
  set: (n: number) => void;
  min: number;
  max: number;
  step: number;
}) {
  return (
    <label className="flex items-center justify-between gap-2 text-xs text-zinc-400">
      <span>{label}</span>
      <input
        type="number"
        value={value}
        min={min}
        max={max}
        step={step}
        onChange={(e) => set(Number(e.target.value))}
        className="w-24 rounded-md border border-zinc-700 bg-zinc-900 px-2 py-1 text-right text-sm text-zinc-100 focus:border-emerald-600 focus:outline-none"
      />
    </label>
  );
}

function Card({ title, subtitle, children }: { title: string; subtitle?: string; children: React.ReactNode }) {
  return (
    <div className="rounded-xl border border-zinc-800 bg-zinc-950 p-5">
      <div className="mb-4">
        <h2 className="text-lg font-semibold text-zinc-100">{title}</h2>
        {subtitle && <p className="text-xs text-zinc-500">{subtitle}</p>}
      </div>
      {children}
    </div>
  );
}

function Placeholder({ text }: { text: string }) {
  return (
    <div className="flex h-48 items-center justify-center rounded-lg border border-dashed border-zinc-800 text-sm text-zinc-600">
      {text}
    </div>
  );
}
