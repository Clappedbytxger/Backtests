"use client";

import { useEffect, useState } from "react";
import { getBuckets, getStrategies, type Strategy } from "@/lib/api";

export default function Home() {
  const [strategies, setStrategies] = useState<Strategy[]>([]);
  const [buckets, setBuckets] = useState<Record<string, number>>({});
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([getStrategies(), getBuckets()])
      .then(([s, b]) => {
        setStrategies(s);
        setBuckets(b.buckets);
      })
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false));
  }, []);

  return (
    <main className="mx-auto max-w-6xl p-8">
      <h1 className="text-3xl font-semibold tracking-tight">Quant-OS</h1>
      <p className="mt-1 text-sm text-zinc-400">
        Strategy registry · {strategies.length} strategies
      </p>

      {loading && <p className="mt-8 text-zinc-400">Loading…</p>}

      {error && (
        <div className="mt-8 rounded-lg border border-red-900 bg-red-950/40 p-4 text-sm text-red-300">
          API not reachable ({error}). Start it with{" "}
          <code className="text-red-200">uvicorn apps.api.main:app</code>, and build
          the registry first with{" "}
          <code className="text-red-200">python scripts/build_registry.py</code>.
        </div>
      )}

      {!loading && !error && (
        <>
          <div className="mt-8 grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-8">
            {Object.entries(buckets).map(([k, v]) => (
              <div
                key={k}
                className="rounded-lg border border-zinc-800 bg-zinc-900/60 p-3"
              >
                <div className="text-2xl font-semibold">{v}</div>
                <div className="text-xs text-zinc-400">{k}</div>
              </div>
            ))}
          </div>

          <table className="mt-8 w-full text-left text-sm">
            <thead className="text-zinc-400">
              <tr className="border-b border-zinc-800">
                <th className="py-2 pr-4 font-medium">#</th>
                <th className="py-2 pr-4 font-medium">Name</th>
                <th className="py-2 pr-4 font-medium">Bucket</th>
                <th className="py-2 pr-4 text-right font-medium">Sharpe</th>
              </tr>
            </thead>
            <tbody>
              {strategies.map((s) => (
                <tr
                  key={s.num}
                  className="border-b border-zinc-900 hover:bg-zinc-900/40"
                >
                  <td className="py-1.5 pr-4 font-mono text-zinc-400">{s.num}</td>
                  <td className="py-1.5 pr-4">{s.name ?? s.slug ?? "—"}</td>
                  <td className="py-1.5 pr-4">
                    <span className="rounded bg-zinc-800 px-2 py-0.5 text-xs">
                      {s.bucket}
                    </span>
                  </td>
                  <td className="py-1.5 pr-4 text-right font-mono">
                    {s.sharpe != null ? s.sharpe.toFixed(2) : "–"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
    </main>
  );
}
