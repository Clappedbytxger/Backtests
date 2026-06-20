"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  getOverview,
  getStrategies,
  type Overview,
  type Strategy,
} from "@/lib/api";

function histogram(values: number[], min = -4, max = 3, step = 0.5) {
  const bins: { name: string; count: number }[] = [];
  for (let lo = min; lo < max; lo += step) {
    bins.push({
      name: lo.toFixed(1),
      count: values.filter((v) => v >= lo && v < lo + step).length,
    });
  }
  return bins;
}

const BUCKET_COLOR: Record<string, string> = {
  validated: "#22c55e",
  candidate: "#84cc16",
  testing: "#eab308",
  overlay: "#3b82f6",
  deferred: "#a855f7",
  done: "#64748b",
  rejected: "#52525b",
};

export default function Home() {
  const [ov, setOv] = useState<Overview | null>(null);
  const [strategies, setStrategies] = useState<Strategy[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([getOverview(), getStrategies()])
      .then(([o, s]) => {
        setOv(o);
        setStrategies(s);
      })
      .catch((e) => setError(String(e)));
  }, []);

  if (error) {
    return (
      <main className="mx-auto max-w-6xl p-8">
        <div className="rounded-lg border border-red-900 bg-red-950/40 p-4 text-sm text-red-300">
          API not reachable ({error}). Start it with{" "}
          <code className="text-red-200">uvicorn apps.api.main:app</code> and build the
          registry with <code className="text-red-200">python scripts/build_registry.py</code>.
        </div>
      </main>
    );
  }
  if (!ov) return <main className="mx-auto max-w-6xl p-8 text-zinc-400">Loading…</main>;

  const bucketData = Object.entries(ov.buckets).map(([name, value]) => ({ name, value }));
  const categoryData = Object.entries(ov.categories)
    .slice(0, 10)
    .map(([name, value]) => ({ name, value }));
  const sharpeHist = histogram(ov.sharpes);

  return (
    <main className="mx-auto max-w-6xl p-8">
      <h1 className="text-3xl font-semibold tracking-tight">Research Dashboard</h1>
      <p className="mt-1 text-sm text-zinc-400">{ov.n_strategies} strategies in the registry</p>

      {/* lifecycle buckets */}
      <div className="mt-8 grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-8">
        {bucketData.map((b) => (
          <div key={b.name} className="rounded-lg border border-zinc-800 bg-zinc-900/60 p-3">
            <div className="text-2xl font-semibold" style={{ color: BUCKET_COLOR[b.name] }}>
              {b.value}
            </div>
            <div className="text-xs capitalize text-zinc-400">{b.name}</div>
          </div>
        ))}
      </div>

      {/* charts */}
      <div className="mt-8 grid gap-6 lg:grid-cols-2">
        <Panel title="Sharpe distribution (catalog, OOS net)">
          <ResponsiveContainer width="100%" height={240}>
            <BarChart data={sharpeHist}>
              <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
              <XAxis dataKey="name" tick={{ fill: "#a1a1aa", fontSize: 11 }} />
              <YAxis tick={{ fill: "#a1a1aa", fontSize: 11 }} allowDecimals={false} />
              <Tooltip contentStyle={{ background: "#18181b", border: "1px solid #3f3f46" }} />
              <Bar dataKey="count" fill="#3b82f6" />
            </BarChart>
          </ResponsiveContainer>
        </Panel>

        <Panel title="Strategies by category">
          <ResponsiveContainer width="100%" height={240}>
            <BarChart data={categoryData} layout="vertical" margin={{ left: 40 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
              <XAxis type="number" tick={{ fill: "#a1a1aa", fontSize: 11 }} allowDecimals={false} />
              <YAxis type="category" dataKey="name" width={90} tick={{ fill: "#a1a1aa", fontSize: 10 }} />
              <Tooltip contentStyle={{ background: "#18181b", border: "1px solid #3f3f46" }} />
              <Bar dataKey="value" fill="#22c55e" />
            </BarChart>
          </ResponsiveContainer>
        </Panel>
      </div>

      {/* top strategies */}
      <h2 className="mt-10 text-lg font-semibold">Top by Sharpe</h2>
      <div className="mt-3 flex flex-wrap gap-2">
        {ov.top.map((t) => (
          <Link
            key={t.num}
            href={`/strategies/${t.num}`}
            className="rounded-lg border border-zinc-800 bg-zinc-900/60 px-3 py-2 hover:border-zinc-600"
          >
            <span className="font-mono text-xs text-zinc-500">{t.num}</span>{" "}
            <span className="text-sm">{t.name}</span>{" "}
            <span className="font-mono text-sm text-emerald-400">{t.sharpe.toFixed(2)}</span>
          </Link>
        ))}
      </div>

      {/* full table */}
      <h2 className="mt-10 text-lg font-semibold">All strategies</h2>
      <table className="mt-3 w-full text-left text-sm">
        <thead className="text-zinc-400">
          <tr className="border-b border-zinc-800">
            <th className="py-2 pr-4 font-medium">#</th>
            <th className="py-2 pr-4 font-medium">Name</th>
            <th className="py-2 pr-4 font-medium">Category</th>
            <th className="py-2 pr-4 font-medium">Bucket</th>
            <th className="py-2 pr-4 text-right font-medium">Sharpe</th>
          </tr>
        </thead>
        <tbody>
          {strategies.map((s) => (
            <tr key={s.num} className="border-b border-zinc-900 hover:bg-zinc-900/40">
              <td className="py-1.5 pr-4 font-mono text-zinc-400">
                <Link href={`/strategies/${s.num}`} className="hover:text-zinc-100">
                  {s.num}
                </Link>
              </td>
              <td className="py-1.5 pr-4">
                <Link href={`/strategies/${s.num}`} className="hover:underline">
                  {s.name ?? s.slug ?? "—"}
                </Link>
              </td>
              <td className="py-1.5 pr-4 text-zinc-400">{s.category ?? "—"}</td>
              <td className="py-1.5 pr-4">
                <span
                  className="rounded px-2 py-0.5 text-xs"
                  style={{ background: (BUCKET_COLOR[s.bucket ?? ""] ?? "#3f3f46") + "33" }}
                >
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
    </main>
  );
}

function Panel({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-lg border border-zinc-800 bg-zinc-900/40 p-4">
      <h3 className="mb-3 text-sm font-medium text-zinc-300">{title}</h3>
      {children}
    </div>
  );
}
