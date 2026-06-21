"use client";

import { useEffect, useRef, useState } from "react";
import {
  agentEvaluate,
  agentPromote,
  agentRun,
  getAgentJob,
  type AgentJob,
  type AgentResult,
  type PromoteResult,
} from "@/lib/api";

const pct = (x?: number | null, d = 1) => (x == null ? "–" : `${(x * 100).toFixed(d)}%`);
const num = (x?: number | null, d = 2) => (x == null ? "–" : x.toFixed(d));

const PLOT_TITLES: Record<string, string> = {
  "01_equity": "Equity curve vs Buy & Hold + S&P 500",
  "02_drawdown": "Drawdown (underwater)",
  "03_monthly": "Monthly returns heatmap",
  "04_permutation": "Monte-Carlo permutation test",
  "05_montecarlo": "Monte-Carlo block bootstrap — Sharpe distribution",
  "06_robustness": "Robustness heatmap — Sharpe across signal lag × cost",
  "07_paramheatmap": "Parameter heatmap — Sharpe across the two parameters",
};
const plotTitle = (key: string) =>
  PLOT_TITLES[key] ?? key.replace(/^\d+_/, "").replace(/_/g, " ");

function metricCards(s: Record<string, number>) {
  return [
    { label: "CAGR", value: pct(s.cagr) },
    { label: "Sharpe", value: num(s.sharpe) },
    { label: "Sortino", value: num(s.sortino) },
    { label: "Calmar", value: num(s.calmar) },
    { label: "Max DD", value: pct(s.max_drawdown) },
    { label: "DD duration", value: s.max_drawdown_duration_days != null ? `${s.max_drawdown_duration_days}d` : "–" },
    { label: "Volatility", value: pct(s.annual_volatility) },
    { label: "Win rate", value: pct(s.win_rate) },
    { label: "Profit factor", value: num(s.profit_factor) },
    { label: "Payoff", value: num(s.payoff_ratio) },
    { label: "Expectancy", value: s.expectancy != null ? `${(s.expectancy * 100).toFixed(2)}%` : "–" },
    { label: "Avg holding", value: s.avg_holding_days != null ? `${s.avg_holding_days.toFixed(1)}d` : "–" },
    { label: "# Trades", value: s.n_trades != null ? String(s.n_trades) : "–" },
  ];
}

export default function AgentPage() {
  const [hypothesis, setHypothesis] = useState("");
  const [dryRun, setDryRun] = useState(false);
  const [job, setJob] = useState<AgentJob | null>(null);
  const [liveRes, setLiveRes] = useState<AgentResult | null>(null);
  const [paramVals, setParamVals] = useState<Record<string, number>>({});
  const [evaluating, setEvaluating] = useState(false);
  const [promote, setPromote] = useState<PromoteResult | null>(null);
  const [promoting, setPromoting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [running, setRunning] = useState(false);
  const pollRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const evalRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const jobIdRef = useRef<string | null>(null);

  function poll(jobId: string) {
    jobIdRef.current = jobId;
    getAgentJob(jobId)
      .then((j) => {
        setJob(j);
        if (j.status === "running") {
          pollRef.current = setTimeout(() => poll(jobId), 1500);
        } else {
          setRunning(false);
          if (j.result) {
            setLiveRes(j.result);
            setParamVals(j.result.params ?? {});
          }
        }
      })
      .catch((e) => {
        setError(String(e));
        setRunning(false);
      });
  }

  useEffect(() => {
    const jid = new URLSearchParams(window.location.search).get("job");
    if (jid) {
      setRunning(true);
      poll(jid);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function run() {
    setError(null);
    setJob(null);
    setLiveRes(null);
    setPromote(null);
    setRunning(true);
    try {
      const { job_id } = await agentRun(hypothesis, dryRun);
      poll(job_id);
    } catch (e) {
      setError(String(e));
      setRunning(false);
    }
  }

  function onSlider(name: string, value: number) {
    const next = { ...paramVals, [name]: value };
    setParamVals(next);
    if (evalRef.current) clearTimeout(evalRef.current);
    evalRef.current = setTimeout(() => doEval(next), 400);
  }

  async function doEval(vals: Record<string, number>) {
    if (!jobIdRef.current) return;
    setEvaluating(true);
    try {
      const r = await agentEvaluate(jobIdRef.current, vals);
      if (r.ok) {
        setLiveRes((prev) =>
          prev
            ? {
                ...prev,
                summary: r.summary,
                vs_benchmark: r.vs_benchmark,
                warning: r.warning,
                plots: { ...prev.plots, ...r.plots },
              }
            : prev,
        );
      }
    } catch {
      /* keep the previous result on a failed live eval */
    } finally {
      setEvaluating(false);
    }
  }

  async function doPromote() {
    if (!jobIdRef.current) return;
    setPromoting(true);
    setError(null);
    try {
      setPromote(await agentPromote(jobIdRef.current));
    } catch (e) {
      setError(String(e));
    } finally {
      setPromoting(false);
    }
  }

  const res = liveRes;
  const base = job?.result;
  const s = res?.summary;
  const hasParams = !!base?.param_grid && Object.keys(base.param_grid).length > 0;

  return (
    <main className="mx-auto max-w-4xl p-8">
      <h1 className="text-2xl font-semibold">Agent — test a hypothesis</h1>
      <p className="mt-1 text-sm text-zinc-400">
        The local model writes only the signal; a fixed harness computes all metrics, the
        equity curve vs S&amp;P 500, the permutation test, bootstrap CI, DSR and the plots.
        Daily bars only · sandboxed (your repo is never modified).
      </p>

      <textarea
        value={hypothesis}
        onChange={(e) => setHypothesis(e.target.value)}
        placeholder="e.g. A 50/200-day SMA trend filter on QQQ, net of costs"
        rows={3}
        className="mt-4 w-full rounded-lg border border-zinc-800 bg-zinc-900/60 p-3 text-sm outline-none focus:border-zinc-600"
      />
      <div className="mt-3 flex flex-wrap items-center gap-4">
        <label className="flex items-center gap-2 text-sm text-zinc-300">
          <input type="checkbox" checked={dryRun} onChange={(e) => setDryRun(e.target.checked)} />
          dry-run (code only, no metrics)
        </label>
        <button
          onClick={run}
          disabled={running || !hypothesis.trim()}
          className="rounded-lg bg-emerald-600 px-4 py-1.5 text-sm font-medium text-white hover:bg-emerald-500 disabled:opacity-40"
        >
          {running ? "Running…" : "Run Agent"}
        </button>
      </div>

      {running && (
        <p className="mt-6 animate-pulse text-sm text-zinc-400">
          Agent is working… (model + backtest + significance; ~1–2 min). status: {job?.status ?? "starting"}
        </p>
      )}
      {error && (
        <div className="mt-6 rounded-lg border border-red-900 bg-red-950/40 p-4 text-sm text-red-300">
          Error: {error}
        </div>
      )}
      {job?.status === "error" && (
        <div className="mt-6 rounded-lg border border-red-900 bg-red-950/40 p-4 text-sm text-red-300">
          Agent failed: {job.error}
        </div>
      )}

      {res && (
        <div className="mt-8 space-y-6">
          {res.warning && (
            <div className="rounded-lg border border-amber-800 bg-amber-950/30 p-4 text-sm text-amber-300">
              ⚠ {res.warning}
            </div>
          )}

          <div className="flex flex-wrap items-center gap-3">
            {res.dups?.length > 0 &&
              res.dups.map(([id, sim]) => (
                <span key={id} className="rounded bg-zinc-800 px-2 py-1 font-mono text-xs" title="resembles existing catalog strategy">
                  ≈ {id} · {sim.toFixed(2)}
                </span>
              ))}
            {base?.signal_code && s && (
              <button
                onClick={doPromote}
                disabled={promoting}
                className="rounded-lg border border-emerald-700 px-3 py-1.5 text-sm text-emerald-300 hover:bg-emerald-950/40 disabled:opacity-50"
              >
                {promoting ? "Adding…" : "+ Add to catalog"}
              </button>
            )}
            {promote?.ok && (
              <span className="text-xs text-emerald-400">
                Added as {promote.num} on <code>{promote.branch}</code> — review &amp; merge.
              </span>
            )}
          </div>

          {s && (
            <>
              <section>
                <h2 className="text-sm font-semibold">
                  Metrics{res.instrument ? ` · ${res.instrument}` : ""}{" "}
                  <span className="text-xs text-zinc-500">(OOS, net of costs)</span>
                </h2>
                <div className="mt-2 grid grid-cols-3 gap-2 sm:grid-cols-5 lg:grid-cols-7">
                  {metricCards(s).map((c) => (
                    <div key={c.label} className="rounded-lg border border-zinc-800 bg-zinc-900/60 p-2.5">
                      <div className="font-mono text-base font-semibold">{c.value}</div>
                      <div className="text-[10px] text-zinc-400">{c.label}</div>
                    </div>
                  ))}
                </div>
              </section>

              {hasParams && (
                <section>
                  <h2 className="text-sm font-semibold">
                    Parameters {evaluating && <span className="text-xs text-emerald-400">updating…</span>}
                  </h2>
                  <div className="mt-2 space-y-2.5">
                    {Object.entries(base!.param_grid!).map(([name, grid]) => {
                      const lo = Math.min(...grid);
                      const hi = Math.max(...grid);
                      const v = paramVals[name] ?? grid[0];
                      return (
                        <div key={name} className="flex items-center gap-3">
                          <label className="w-24 text-sm text-zinc-300">{name}</label>
                          <input
                            type="range"
                            min={lo}
                            max={hi}
                            step={1}
                            value={v}
                            onChange={(e) => onSlider(name, Number(e.target.value))}
                            className="flex-1 accent-emerald-500"
                          />
                          <span className="w-12 text-right font-mono text-sm">{v}</span>
                        </div>
                      );
                    })}
                  </div>
                  <p className="mt-1.5 text-xs text-zinc-500">
                    Drag to re-run the backtest live — metrics, equity, drawdown and monthly update;
                    significance &amp; heatmaps stay from the full run.
                  </p>
                </section>
              )}

              <section>
                <h2 className="text-sm font-semibold">Significance</h2>
                <div className="mt-2 grid grid-cols-2 gap-2 sm:grid-cols-4">
                  <Stat label="Permutation p" value={num(res.permutation?.p_value, 3)} />
                  <Stat label="Observed Sharpe" value={num(res.permutation?.observed)} />
                  <Stat label="Bootstrap Sharpe CI" value={`[${num(res.bootstrap_ci?.ci_low)}, ${num(res.bootstrap_ci?.ci_high)}]`} />
                  <Stat label="DSR" value={num(res.deflated_sharpe?.psr_deflated, 3)} />
                </div>
              </section>

              {res.plots && Object.keys(res.plots).length > 0 && (
                <section className="space-y-5">
                  <h2 className="text-sm font-semibold">Visualizations</h2>
                  {Object.entries(res.plots)
                    .sort(([a], [b]) => a.localeCompare(b))
                    .map(([key, b64]) => (
                      <figure key={key}>
                        <figcaption className="mb-1.5 text-xs font-medium text-zinc-300">{plotTitle(key)}</figcaption>
                        {/* eslint-disable-next-line @next/next/no-img-element */}
                        <img
                          src={`data:image/png;base64,${b64}`}
                          alt={plotTitle(key)}
                          className="w-full rounded-lg border border-zinc-800 bg-white"
                        />
                      </figure>
                    ))}
                </section>
              )}

              {res.vs_benchmark && (
                <section>
                  <h2 className="text-sm font-semibold">Total return vs benchmarks</h2>
                  <div className="mt-2 grid grid-cols-3 gap-2">
                    <Stat label="Strategy" value={pct(res.vs_benchmark.strategy_total_return)} />
                    <Stat label={`Buy & Hold ${res.instrument ?? ""}`} value={pct(res.vs_benchmark.buy_hold_total_return)} />
                    <Stat label="S&P 500" value={pct(res.vs_benchmark.sp500_total_return)} />
                  </div>
                </section>
              )}
            </>
          )}

          {!s && res.status === "no-metrics" && (
            <div className="rounded-lg border border-amber-900 bg-amber-950/30 p-4 text-sm text-amber-300">
              The generated strategy ran but produced no metrics.
              <pre className="mt-2 overflow-auto whitespace-pre-wrap text-xs text-amber-200/80">
                {res.stdout_tail || "(no output)"}
              </pre>
            </div>
          )}

          {base?.signal_code && (
            <section>
              <h2 className="text-sm font-semibold">
                Signal written by the model{" "}
                <span className="font-mono text-xs text-zinc-500">({base.branch})</span>
              </h2>
              <pre className="mt-2 overflow-auto rounded-lg border border-zinc-800 bg-zinc-950 p-3 text-xs leading-relaxed text-zinc-200">
                {base.signal_code}
              </pre>
            </section>
          )}

          {res.run_py && (
            <details className="rounded-lg border border-zinc-800 bg-zinc-900/40 p-3">
              <summary className="cursor-pointer text-sm text-zinc-300">Full run.py (signal + fixed harness)</summary>
              <pre className="mt-2 max-h-[28rem] overflow-auto text-xs leading-relaxed text-zinc-300">{res.run_py}</pre>
            </details>
          )}
        </div>
      )}
    </main>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-zinc-800 bg-zinc-900/60 p-2.5">
      <div className="font-mono text-sm font-semibold">{value}</div>
      <div className="text-[10px] text-zinc-400">{label}</div>
    </div>
  );
}
