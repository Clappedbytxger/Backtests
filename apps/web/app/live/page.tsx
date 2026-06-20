"use client";

import { useCallback, useEffect, useState } from "react";
import { getLiveBook, type LiveBook } from "@/lib/api";

function fmt(v: unknown): string {
  return typeof v === "number" ? v.toFixed(1) : v != null ? String(v) : "–";
}

export default function LivePage() {
  const [book, setBook] = useState<LiveBook | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback((refresh = false) => {
    setLoading(true);
    setError(null);
    getLiveBook(refresh)
      .then(setBook)
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    load(false);
  }, [load]);

  return (
    <main className="mx-auto max-w-5xl p-8">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Live Book — 0108 CTI CORE</h1>
          <p className="mt-1 text-sm text-zinc-400">
            Target positions today (frozen inverse-vol book, 6% target vol)
            {book?.asof ? ` · as of ${book.asof}` : ""}
          </p>
        </div>
        <button
          onClick={() => load(true)}
          disabled={loading}
          className="rounded-lg border border-zinc-700 px-3 py-1.5 text-sm hover:bg-zinc-900 disabled:opacity-50"
        >
          {loading ? "…" : "Refresh"}
        </button>
      </div>

      {loading && !book && (
        <p className="mt-8 text-zinc-400">
          Computing live signal… (pulls market data; the first call can take a moment)
        </p>
      )}
      {error && (
        <div className="mt-8 rounded-lg border border-red-900 bg-red-950/40 p-4 text-sm text-red-300">
          API not reachable ({error}). Start it with{" "}
          <code className="text-red-200">uvicorn apps.api.main:app</code>.
        </div>
      )}
      {book && !book.ok && (
        <div className="mt-8 rounded-lg border border-amber-900 bg-amber-950/30 p-4 text-sm text-amber-300">
          Signal compute failed: {book.error}
        </div>
      )}

      {book && book.ok && (
        <>
          <div className="mt-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
            <Stat label="Book Sharpe (IS)" value={book.book_sharpe?.toFixed(2)} />
            <Stat
              label="Gross exposure"
              value={book.gross_exposure_pct != null ? `${book.gross_exposure_pct}%` : "–"}
            />
            <Stat label="VIX" value={fmt(book.context?.vix)} />
            <Stat label="Crypto gate" value={fmt(book.context?.crypto_gate)} />
          </div>

          <div className="mt-4 flex flex-wrap gap-2 text-xs">
            <Flag on={Boolean(book.context?.month_end)} label="month-end FX" />
            <Flag on={Boolean(book.context?.carry_on)} label="carry risk-on" />
            {book.cached && <span className="text-zinc-500">cached</span>}
          </div>

          <h2 className="mt-8 text-lg font-semibold">Target positions</h2>
          {book.positions && book.positions.length > 0 ? (
            <table className="mt-3 w-full max-w-md text-left text-sm">
              <thead className="text-zinc-400">
                <tr className="border-b border-zinc-800">
                  <th className="py-2 pr-4 font-medium">Instrument</th>
                  <th className="py-2 text-right font-medium">% of equity</th>
                </tr>
              </thead>
              <tbody>
                {book.positions.map((p) => (
                  <tr key={p.instrument} className="border-b border-zinc-900">
                    <td className="py-1.5 pr-4 font-mono">{p.instrument}</td>
                    <td
                      className={`py-1.5 text-right font-mono ${
                        p.weight_pct >= 0 ? "text-emerald-400" : "text-red-400"
                      }`}
                    >
                      {p.weight_pct >= 0 ? "+" : ""}
                      {p.weight_pct.toFixed(2)}%
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <p className="mt-3 text-sm text-zinc-400">Flat — no active positions today.</p>
          )}
        </>
      )}
    </main>
  );
}

function Stat({ label, value }: { label: string; value?: string | null }) {
  return (
    <div className="rounded-lg border border-zinc-800 bg-zinc-900/60 p-3">
      <div className="font-mono text-lg font-semibold">{value ?? "–"}</div>
      <div className="text-xs text-zinc-400">{label}</div>
    </div>
  );
}

function Flag({ on, label }: { on: boolean; label: string }) {
  return (
    <span
      className={`rounded px-2 py-0.5 ${
        on ? "bg-emerald-900/50 text-emerald-300" : "bg-zinc-800 text-zinc-500"
      }`}
    >
      {label}
    </span>
  );
}
