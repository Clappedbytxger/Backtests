"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { getPlots, getStrategy, plotUrl, type StrategyDetail } from "@/lib/api";

export default function StrategyPage() {
  const params = useParams<{ num: string }>();
  const num = params.num;
  const [s, setS] = useState<StrategyDetail | null>(null);
  const [plots, setPlots] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!num) return;
    getStrategy(num).then(setS).catch((e) => setError(String(e)));
    getPlots(num).then((r) => setPlots(r.plots)).catch(() => {});
  }, [num]);

  if (error) return <main className="mx-auto max-w-5xl p-8 text-red-300">Error: {error}</main>;
  if (!s) return <main className="mx-auto max-w-5xl p-8 text-zinc-400">Loading…</main>;

  return (
    <main className="mx-auto max-w-5xl p-8">
      <Link href="/" className="text-sm text-zinc-400 hover:text-zinc-100">
        ← back
      </Link>
      <h1 className="mt-2 text-2xl font-semibold">
        <span className="font-mono text-zinc-500">{s.num}</span> {s.name ?? s.slug}
      </h1>
      <div className="mt-2 flex flex-wrap items-center gap-2 text-sm">
        {s.bucket && <Badge>{s.bucket}</Badge>}
        {s.category && <Badge>{s.category}</Badge>}
        {s.status && <span className="text-zinc-400">{s.status}</span>}
      </div>

      {s.hypothesis && (
        <p className="mt-4 text-sm text-zinc-300">
          <span className="text-zinc-500">Hypothesis: </span>
          {s.hypothesis}
        </p>
      )}
      {s.note && <p className="mt-2 text-sm text-zinc-400">{s.note}</p>}

      <div className="mt-6 grid grid-cols-2 gap-3 sm:grid-cols-5">
        <Stat label="Sharpe" value={s.sharpe?.toFixed(2)} />
        <Stat label="CAGR" value={s.cagr} />
        <Stat label="MaxDD" value={s.maxdd} />
        <Stat label="p-value" value={s.p_value?.toFixed(3)} />
        <Stat label="DSR" value={s.dsr?.toFixed(2)} />
      </div>

      {Object.keys(s.metrics).length > 0 && (
        <>
          <h2 className="mt-8 text-lg font-semibold">metrics.json</h2>
          <table className="mt-2 text-sm">
            <tbody>
              {Object.entries(s.metrics).map(([k, v]) => (
                <tr key={k} className="border-b border-zinc-900">
                  <td className="py-1 pr-6 font-mono text-zinc-400">{k}</td>
                  <td className="py-1 font-mono">{String(v)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}

      {plots.length > 0 && (
        <>
          <h2 className="mt-8 text-lg font-semibold">Plots</h2>
          <div className="mt-3 grid gap-4">
            {plots.map((p) => (
              /* eslint-disable-next-line @next/next/no-img-element */
              <img
                key={p}
                src={plotUrl(num, p)}
                alt={p}
                className="rounded-lg border border-zinc-800"
              />
            ))}
          </div>
        </>
      )}
    </main>
  );
}

function Badge({ children }: { children: React.ReactNode }) {
  return <span className="rounded bg-zinc-800 px-2 py-0.5 text-xs">{children}</span>;
}

function Stat({ label, value }: { label: string; value?: string | null }) {
  return (
    <div className="rounded-lg border border-zinc-800 bg-zinc-900/60 p-3">
      <div className="font-mono text-lg font-semibold">{value ?? "–"}</div>
      <div className="text-xs text-zinc-400">{label}</div>
    </div>
  );
}
