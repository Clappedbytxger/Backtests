"use client";

import { useCallback, useEffect, useState } from "react";
import {
  factoryAssetUrl,
  getFactoryPending,
  getFactoryRejects,
  getFactoryState,
  getFactoryReport,
  stopFactory,
  type FactoryStateResponse,
  type PendingReport,
  type RejectItem,
} from "@/lib/api";
import ReportMarkdown from "./ReportMarkdown";

export default function FactoryPage() {
  const [state, setState] = useState<FactoryStateResponse | null>(null);
  const [pending, setPending] = useState<PendingReport[]>([]);
  const [rejects, setRejects] = useState<RejectItem[]>([]);
  const [rejectCount, setRejectCount] = useState(0);
  const [open, setOpen] = useState<{ name: string; markdown: string; plots: string[] } | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(() => {
    getFactoryState().then(setState).catch((e) => setError(String(e)));
    getFactoryPending().then((r) => setPending(r.reports)).catch(() => {});
    getFactoryRejects(40).then((r) => { setRejects(r.items); setRejectCount(r.count); }).catch(() => {});
  }, []);

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, 5000); // live poll
    return () => clearInterval(id);
  }, [refresh]);

  if (error)
    return (
      <main className="mx-auto max-w-6xl p-8">
        <div className="rounded-lg border border-red-900 bg-red-950/40 p-4 text-sm text-red-300">
          API nicht erreichbar ({error}). Starte sie mit <code>uvicorn apps.api.main:app</code>.
        </div>
      </main>
    );

  const s = state?.state;
  const running = state?.running ?? false;

  return (
    <main className="mx-auto max-w-6xl p-8">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-semibold tracking-tight">Alpha Factory</h1>
          <p className="mt-1 text-sm text-zinc-400">
            Autonomer Research-Loop · vorselektierte Strategien zur manuellen Prüfung
          </p>
        </div>
        <div className="flex items-center gap-3">
          <span className={`flex items-center gap-2 rounded-full border px-3 py-1 text-xs ${running ? "border-emerald-600 text-emerald-300" : "border-zinc-700 text-zinc-400"}`}>
            <span className={`h-2 w-2 rounded-full ${running ? "animate-pulse bg-emerald-400" : "bg-zinc-500"}`} />
            {running ? "läuft" : "gestoppt"}
          </span>
          <button
            onClick={() => stopFactory().then(refresh)}
            disabled={!running || state?.stop_pending}
            className="rounded-md border border-red-800 bg-red-950/40 px-3 py-1.5 text-xs text-red-200 hover:border-red-600 disabled:opacity-40"
          >
            {state?.stop_pending ? "Stop angefordert…" : "Stop"}
          </button>
        </div>
      </div>

      {!state?.exists && (
        <div className="mt-6 rounded-lg border border-zinc-800 bg-zinc-900/40 p-4 text-sm text-zinc-400">
          Noch kein Worker-Lauf gefunden. Starte ihn mit{" "}
          <code className="text-zinc-200">.venv/Scripts/python.exe -m agent.alpha_factory</code>.
        </div>
      )}

      {/* counters */}
      <div className="mt-6 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
        <Stat label="Iterationen" value={s?.iterations ?? 0} />
        <Stat label="Passed" value={s?.passed ?? 0} accent="text-emerald-400" />
        <Stat label="Rejected" value={s?.rejected ?? 0} accent="text-zinc-400" />
        <Stat label="Errors" value={s?.errored ?? 0} accent="text-amber-400" />
        <Stat label="RAM (MB)" value={s?.rss_mb ? Math.round(s.rss_mb) : "—"} />
        <Stat label="Ø Iter (s)" value={s?.last_iter_s ?? "—"} />
      </div>

      <div className="mt-8 grid gap-8 lg:grid-cols-[1fr_320px]">
        {/* pending reports + viewer */}
        <section>
          <h2 className="text-lg font-semibold">
            Pending Review <span className="text-sm font-normal text-zinc-500">({pending.length})</span>
          </h2>
          {pending.length === 0 ? (
            <p className="mt-2 text-sm text-zinc-500">
              Noch keine Strategie hat das strikte Gate passiert. Das ist normal — der Loop verwirft die
              allermeisten Hypothesen.
            </p>
          ) : (
            <div className="mt-3 space-y-2">
              {pending.map((r) => (
                <button
                  key={r.name}
                  onClick={() => getFactoryReport(r.name).then(setOpen)}
                  className={`block w-full rounded-lg border px-4 py-2.5 text-left transition ${
                    open?.name === r.name ? "border-emerald-600 bg-emerald-500/5" : "border-zinc-800 bg-zinc-900/40 hover:border-zinc-600"
                  }`}
                >
                  <div className="text-sm font-medium text-zinc-100">{r.title}</div>
                  <div className="font-mono text-xs text-zinc-500">{r.name} · {r.mtime.slice(0, 16).replace("T", " ")}</div>
                </button>
              ))}
            </div>
          )}

          {open && (
            <article className="mt-6 rounded-xl border border-zinc-800 bg-zinc-950 p-6">
              <ReportMarkdown markdown={open.markdown} />
              {open.plots.length > 0 && (
                <div className="mt-6 border-t border-zinc-800 pt-4">
                  <div className="mb-3 text-xs font-medium uppercase tracking-wide text-zinc-500">Plots</div>
                  <div className="grid gap-3 sm:grid-cols-2">
                    {open.plots.map((p) => (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img key={p} src={factoryAssetUrl(open.name, p)} alt={p} className="rounded-lg border border-zinc-800" />
                    ))}
                  </div>
                </div>
              )}
            </article>
          )}
        </section>

        {/* reject feed */}
        <aside className="lg:sticky lg:top-6 lg:self-start">
          <h2 className="text-lg font-semibold">
            Verworfen <span className="text-sm font-normal text-zinc-500">({rejectCount})</span>
          </h2>
          <p className="mb-3 text-xs text-zinc-500">Letzte Hypothesen, die das Gate nicht bestanden (Dedup-Log).</p>
          <div className="max-h-[70vh] space-y-1.5 overflow-y-auto pr-1">
            {rejects.map((r, i) => (
              <div key={i} className="rounded-lg border border-zinc-800 bg-zinc-900/40 p-2.5 text-xs">
                <div className="font-mono text-zinc-300">{r.slug}</div>
                <div className="mt-0.5 text-red-300/80">{r.reason}</div>
                {(r.sharpe != null || r.oos_sharpe != null) && (
                  <div className="mt-0.5 text-zinc-500">
                    Sh {fmt(r.sharpe)} · OOS {fmt(r.oos_sharpe)} · p {fmt(r.perm_p, 3)} · {r.n_trades ?? "—"} Trades
                  </div>
                )}
              </div>
            ))}
            {rejects.length === 0 && <p className="text-sm text-zinc-600">—</p>}
          </div>
        </aside>
      </div>
    </main>
  );
}

function fmt(x: number | null, d = 2) {
  return typeof x === "number" ? x.toFixed(d) : "—";
}

function Stat({ label, value, accent }: { label: string; value: string | number; accent?: string }) {
  return (
    <div className="rounded-lg border border-zinc-800 bg-zinc-900/60 p-3 text-center">
      <div className={`text-2xl font-semibold ${accent ?? "text-zinc-100"}`}>{value}</div>
      <div className="text-[11px] uppercase tracking-wide text-zinc-500">{label}</div>
    </div>
  );
}
