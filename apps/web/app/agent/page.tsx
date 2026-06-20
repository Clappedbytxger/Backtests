"use client";

import { useEffect, useRef, useState } from "react";
import { agentRun, getAgentJob, type AgentJob } from "@/lib/api";

export default function AgentPage() {
  const [hypothesis, setHypothesis] = useState("");
  const [dryRun, setDryRun] = useState(true);
  const [job, setJob] = useState<AgentJob | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [running, setRunning] = useState(false);
  const pollRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Deep-link: /agent?job=<id> loads an existing run (shareable / screenshotable).
  useEffect(() => {
    const jid = new URLSearchParams(window.location.search).get("job");
    if (jid) {
      setRunning(true);
      poll(jid);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function poll(jobId: string) {
    getAgentJob(jobId)
      .then((j) => {
        setJob(j);
        if (j.status === "running") {
          pollRef.current = setTimeout(() => poll(jobId), 1500);
        } else {
          setRunning(false);
        }
      })
      .catch((e) => {
        setError(String(e));
        setRunning(false);
      });
  }

  async function run() {
    setError(null);
    setJob(null);
    setRunning(true);
    try {
      const { job_id } = await agentRun(hypothesis, dryRun);
      poll(job_id);
    } catch (e) {
      setError(String(e));
      setRunning(false);
    }
  }

  const res = job?.result;

  return (
    <main className="mx-auto max-w-4xl p-8">
      <h1 className="text-2xl font-semibold">Agent — test a hypothesis</h1>
      <p className="mt-1 text-sm text-zinc-400">
        Runs the autonomous research agent on the local model. Sandboxed — your repo
        and branches are never modified.
      </p>

      <textarea
        value={hypothesis}
        onChange={(e) => setHypothesis(e.target.value)}
        placeholder="e.g. SPY shows a positive turn-of-month effect (last 1 + first 3 trading days) net of costs"
        rows={3}
        className="mt-4 w-full rounded-lg border border-zinc-800 bg-zinc-900/60 p-3 text-sm outline-none focus:border-zinc-600"
      />
      <div className="mt-3 flex flex-wrap items-center gap-4">
        <label className="flex items-center gap-2 text-sm text-zinc-300">
          <input type="checkbox" checked={dryRun} onChange={(e) => setDryRun(e.target.checked)} />
          dry-run (generate code only)
        </label>
        <button
          onClick={run}
          disabled={running || !hypothesis.trim()}
          className="rounded-lg bg-emerald-600 px-4 py-1.5 text-sm font-medium text-white hover:bg-emerald-500 disabled:opacity-40"
        >
          {running ? "Running…" : "Run Agent"}
        </button>
        {!dryRun && (
          <span className="text-xs text-amber-400">runs the backtest in the sandbox</span>
        )}
      </div>

      {running && (
        <p className="mt-6 animate-pulse text-sm text-zinc-400">
          Agent is working… (local model generation can take ~1 min; status:{" "}
          {job?.status ?? "starting"})
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
          {res.dups?.length > 0 && (
            <section>
              <h2 className="text-sm font-semibold text-amber-300">
                ⚠ Resembles existing strategies (catalog de-dup)
              </h2>
              <div className="mt-2 flex flex-wrap gap-2">
                {res.dups.map(([id, sim]) => (
                  <span key={id} className="rounded bg-zinc-800 px-2 py-1 font-mono text-xs">
                    {id} · {sim.toFixed(2)}
                  </span>
                ))}
              </div>
            </section>
          )}

          {res.metrics && (
            <section>
              <h2 className="text-sm font-semibold">Backtest metrics</h2>
              <pre className="mt-2 overflow-x-auto rounded-lg border border-zinc-800 bg-zinc-900/60 p-3 text-xs">
                {JSON.stringify(res.metrics, null, 2)}
              </pre>
            </section>
          )}

          <section>
            <h2 className="text-sm font-semibold">
              Generated run.py{" "}
              <span className="font-mono text-xs text-zinc-500">({res.branch})</span>
            </h2>
            <pre className="mt-2 max-h-[28rem] overflow-auto rounded-lg border border-zinc-800 bg-zinc-950 p-3 text-xs leading-relaxed text-zinc-200">
              {res.run_py || "(empty)"}
            </pre>
          </section>

          {res.report && (
            <section>
              <h2 className="text-sm font-semibold">REPORT.md</h2>
              <pre className="mt-2 whitespace-pre-wrap rounded-lg border border-zinc-800 bg-zinc-900/60 p-3 text-xs">
                {res.report}
              </pre>
            </section>
          )}
        </div>
      )}
    </main>
  );
}
