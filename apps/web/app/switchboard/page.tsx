"use client";

import { useCallback, useEffect, useState } from "react";
import {
  getSwitchboardBenchmarks,
  getSwitchboardMatrix,
  type CellRating,
  type RegimeCode,
  type SwitchboardBenchmark,
  type SwitchboardCell,
  type SwitchboardMatrixResponse,
  type SwitchboardRow,
} from "@/lib/api";

const cls = (...x: (string | false | undefined)[]) => x.filter(Boolean).join(" ");
const num = (v: number | null | undefined, d = 2) =>
  v == null || !isFinite(v) ? "—" : v.toFixed(d);
const pct = (v: number | null | undefined, d = 1) =>
  v == null || !isFinite(v) ? "—" : `${v >= 0 ? "+" : ""}${(v * 100).toFixed(d)}%`;

// Cell tier → Tailwind classes (the four-colour spec: tiefgrün/hellgrün/grau/rot).
const RATING_STYLE: Record<CellRating, { bg: string; text: string; tag: string }> = {
  excellent: { bg: "bg-emerald-600/85", text: "text-emerald-50", tag: "Exzellent" },
  good: { bg: "bg-green-500/40", text: "text-green-100", tag: "Gut" },
  neutral: { bg: "bg-zinc-800/60", text: "text-zinc-500", tag: "Neutral" },
  loss: { bg: "bg-red-600/45", text: "text-red-100", tag: "Verlust" },
};

export default function SwitchboardPage() {
  const [benchmarks, setBenchmarks] = useState<SwitchboardBenchmark[]>([]);
  const [benchmark, setBenchmark] = useState("SPY");
  const [minSharpe, setMinSharpe] = useState(0.8);
  const [minPf, setMinPf] = useState(1.2);
  const [data, setData] = useState<SwitchboardMatrixResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    getSwitchboardBenchmarks()
      .then((r) => setBenchmarks(r.benchmarks))
      .catch(() => {});
  }, []);

  const load = useCallback(
    (b: string, ms: number, mp: number) => {
      setLoading(true);
      setError(null);
      getSwitchboardMatrix({ benchmark: b, minSharpe: ms, minProfitFactor: mp })
        .then((r) => {
          if (!r.ok) throw new Error(r.error ?? "unknown error");
          setData(r);
        })
        .catch((e) => setError(String(e)))
        .finally(() => setLoading(false));
    },
    [],
  );

  useEffect(() => {
    load(benchmark, minSharpe, minPf);
  }, [benchmark, minSharpe, minPf, load]);

  const current = data?.current_regime ?? null;

  return (
    <main className="mx-auto max-w-7xl px-8 py-8">
      <header className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">Switchboard</h1>
          <p className="mt-1 max-w-2xl text-sm text-zinc-400">
            Dynamisches Strategie-Routing: jede Strategie wird nach ihrer{" "}
            <span className="text-zinc-200">regime-spezifischen</span> Performance bewertet
            und nur im aktuell passenden Marktregime live geschaltet
            (Sharpe&nbsp;&gt;&nbsp;{num(data?.thresholds.min_sharpe ?? minSharpe, 2)} und
            Profit&nbsp;Factor&nbsp;&gt;&nbsp;{num(data?.thresholds.min_profit_factor ?? minPf, 2)}).
          </p>
        </div>
        <div className="flex items-center gap-2 text-xs text-zinc-400">
          <span>Regime-Benchmark</span>
          <select
            value={benchmark}
            onChange={(e) => setBenchmark(e.target.value)}
            className="rounded border border-zinc-700 bg-zinc-900 px-2 py-1.5 text-zinc-100"
          >
            {benchmarks.map((b) => (
              <option key={b.ticker} value={b.ticker}>
                {b.ticker} · {b.name}
              </option>
            ))}
          </select>
        </div>
      </header>

      {/* threshold sliders */}
      <div className="mb-6 flex flex-wrap gap-8 rounded-lg border border-zinc-800 bg-zinc-900/40 px-5 py-4">
        <Slider
          label="Min. Sharpe"
          value={minSharpe}
          min={0}
          max={2}
          step={0.1}
          onChange={setMinSharpe}
        />
        <Slider
          label="Min. Profit Factor"
          value={minPf}
          min={1}
          max={3}
          step={0.1}
          onChange={setMinPf}
        />
        <div className="ml-auto flex items-end gap-5 text-xs text-zinc-400">
          <Legend />
        </div>
      </div>

      {error && (
        <div className="mb-6 rounded-lg border border-red-700/60 bg-red-950/40 px-4 py-3 text-sm text-red-300">
          {error}
        </div>
      )}

      {data && <LiveIndicator data={data} />}

      {data && (
        <Matrix data={data} current={current} loading={loading} />
      )}

      {!data && !error && (
        <div className="py-20 text-center text-sm text-zinc-500">
          {loading ? "Lade Switchboard …" : "Keine Daten."}
        </div>
      )}
    </main>
  );
}

// ── live indicator: the currently active market regime ───────────────────────
function LiveIndicator({ data }: { data: SwitchboardMatrixResponse }) {
  const snap = data.current;
  const sw = data.switch;
  const prev = data.regimes.find((r) => r.code === sw.previous_regime);
  const color = snap.color ?? "#475569";
  return (
    <section
      className="mb-6 overflow-hidden rounded-xl border bg-zinc-900/50"
      style={{ borderColor: color, boxShadow: `0 0 30px -10px ${color}` }}
    >
      <div className="flex flex-wrap items-center gap-x-8 gap-y-4 px-6 py-5">
        <div className="flex items-center gap-3">
          <span className="relative flex h-3 w-3">
            <span
              className="absolute inline-flex h-full w-full animate-ping rounded-full opacity-70"
              style={{ background: color }}
            />
            <span className="relative inline-flex h-3 w-3 rounded-full" style={{ background: color }} />
          </span>
          <div>
            <div className="text-[10px] uppercase tracking-widest text-zinc-500">
              Aktives Marktregime · {data.benchmark}
            </div>
            <div className="text-lg font-semibold" style={{ color }}>
              {snap.label}
            </div>
          </div>
        </div>

        <div className="text-xs text-zinc-400">
          <div className="text-[10px] uppercase tracking-widest text-zinc-600">Richtung</div>
          <div className="text-zinc-200">{snap.direction_label ?? "—"}</div>
        </div>
        <div className="text-xs text-zinc-400">
          <div className="text-[10px] uppercase tracking-widest text-zinc-600">Seit</div>
          <div className="text-zinc-200">
            {sw.since ?? "—"} ({sw.bars_in_regime} Bars)
          </div>
        </div>
        {prev && (
          <div className="text-xs text-zinc-400">
            <div className="text-[10px] uppercase tracking-widest text-zinc-600">Letzter Wechsel</div>
            <div className="flex items-center gap-1.5 text-zinc-200">
              <span style={{ color: prev.color }}>{prev.label}</span>
              <span className="text-zinc-600">→</span>
              <span style={{ color }}>{snap.label}</span>
            </div>
          </div>
        )}

        <div className="ml-auto flex items-center gap-4">
          <Counter value={data.summary.active} label="Live geschaltet" tone="active" />
          <Counter value={data.summary.paused} label="Pausiert" tone="paused" />
        </div>
      </div>
    </section>
  );
}

function Counter({ value, label, tone }: { value: number; label: string; tone: "active" | "paused" }) {
  return (
    <div className="text-center">
      <div
        className={cls(
          "text-2xl font-semibold tabular-nums",
          tone === "active" ? "text-emerald-300" : "text-zinc-400",
        )}
      >
        {value}
      </div>
      <div className="text-[10px] uppercase tracking-widest text-zinc-600">{label}</div>
    </div>
  );
}

// ── the matrix table ─────────────────────────────────────────────────────────
function Matrix({
  data,
  current,
  loading,
}: {
  data: SwitchboardMatrixResponse;
  current: RegimeCode | null;
  loading: boolean;
}) {
  return (
    <section className={cls("overflow-x-auto rounded-xl border border-zinc-800", loading && "opacity-60")}>
      <table className="w-full border-collapse text-sm">
        <thead>
          <tr className="border-b border-zinc-800 bg-zinc-900/70">
            <th className="sticky left-0 z-10 bg-zinc-900/70 px-4 py-3 text-left text-[10px] font-medium uppercase tracking-widest text-zinc-500">
              Strategie
            </th>
            {data.regimes.map((r) => {
              const isCur = r.code === current;
              return (
                <th
                  key={r.code}
                  className={cls(
                    "px-3 py-3 text-center text-[11px] font-medium",
                    isCur ? "text-zinc-100" : "text-zinc-500",
                  )}
                  style={isCur ? { background: `${r.color}22` } : undefined}
                >
                  <div className="flex items-center justify-center gap-1.5">
                    <span className="h-2.5 w-2.5 rounded-sm" style={{ background: r.color }} />
                    {r.label}
                    {isCur && (
                      <span className="rounded bg-zinc-100/10 px-1 text-[8px] uppercase tracking-wide text-zinc-200">
                        live
                      </span>
                    )}
                  </div>
                </th>
              );
            })}
            <th className="px-4 py-3 text-center text-[10px] font-medium uppercase tracking-widest text-zinc-500">
              Status
            </th>
          </tr>
        </thead>
        <tbody>
          {data.rows.map((row) => (
            <Row key={row.label} row={row} regimes={data.regimes} current={current} />
          ))}
        </tbody>
      </table>
    </section>
  );
}

function Row({
  row,
  regimes,
  current,
}: {
  row: SwitchboardRow;
  regimes: { code: RegimeCode; label: string; color: string }[];
  current: RegimeCode | null;
}) {
  const active = row.status === "ACTIVE";
  return (
    <tr className={cls("border-b border-zinc-900 transition-colors hover:bg-zinc-900/40", active && "bg-emerald-950/10")}>
      <td className="sticky left-0 z-10 bg-zinc-950 px-4 py-2.5">
        <div className="flex items-center gap-2">
          <span
            className={cls(
              "h-1.5 w-1.5 shrink-0 rounded-full",
              active ? "bg-emerald-400" : "bg-zinc-700",
            )}
          />
          <div className="min-w-0">
            <div className="truncate text-zinc-100">{row.name}</div>
            <div className="font-mono text-[10px] text-zinc-600">
              #{row.num} · {row.n_total} Bars
            </div>
          </div>
        </div>
      </td>
      {regimes.map((r) => (
        <Cell key={r.code} cell={row.cells[r.code]} isCurrent={r.code === current} />
      ))}
      <td className="px-4 py-2.5 text-center">
        <StatusPill status={row.status} />
      </td>
    </tr>
  );
}

function Cell({ cell, isCurrent }: { cell: SwitchboardCell; isCurrent: boolean }) {
  const style = RATING_STYLE[cell.rating];
  const title =
    `${cell.label}\n` +
    `Sharpe ${num(cell.sharpe)} · Profit Factor ${num(cell.profit_factor)}\n` +
    `Trefferquote ${pct(cell.win_rate)} · MaxDD ${pct(cell.max_drawdown)}\n` +
    `Return ${pct(cell.total_return)} · ${cell.n} Bars (${pct(cell.pct_of_time, 0)} der Zeit)\n` +
    `${cell.qualified ? "✓ qualifiziert" : "✗ nicht qualifiziert"}`;
  return (
    <td
      className={cls("px-2 py-1.5", isCurrent && "ring-1 ring-inset ring-zinc-100/30")}
      title={title}
    >
      <div className={cls("rounded-md px-2 py-1.5 text-center", style.bg, style.text)}>
        {cell.n < 1 ? (
          <span className="text-[11px] text-zinc-600">—</span>
        ) : (
          <>
            <div className="flex items-center justify-center gap-2 font-mono text-xs tabular-nums">
              <span title="Sharpe">S {num(cell.sharpe, 1)}</span>
              <span className="opacity-50">·</span>
              <span title="Profit Factor">PF {num(cell.profit_factor, 1)}</span>
            </div>
            <div className="mt-0.5 font-mono text-[9px] opacity-70">
              {pct(cell.win_rate, 0)} WR · {pct(cell.max_drawdown, 0)} DD
            </div>
          </>
        )}
      </div>
    </td>
  );
}

function StatusPill({ status }: { status: "ACTIVE" | "PAUSED" }) {
  if (status === "ACTIVE")
    return (
      <span className="inline-flex items-center gap-1.5 rounded-full border border-emerald-600/60 bg-emerald-500/10 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-wider text-emerald-300">
        <span className="relative flex h-1.5 w-1.5">
          <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75" />
          <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-emerald-400" />
        </span>
        Active
      </span>
    );
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full border border-zinc-700 bg-zinc-800/40 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-wider text-zinc-500">
      <span className="h-1.5 w-1.5 rounded-full bg-zinc-600" />
      Paused
    </span>
  );
}

// ── small controls ───────────────────────────────────────────────────────────
function Slider({
  label,
  value,
  min,
  max,
  step,
  onChange,
}: {
  label: string;
  value: number;
  min: number;
  max: number;
  step: number;
  onChange: (v: number) => void;
}) {
  return (
    <label className="flex flex-col gap-1 text-xs text-zinc-400">
      <span className="flex items-center justify-between gap-4">
        <span>{label}</span>
        <span className="font-mono text-zinc-200">{value.toFixed(1)}</span>
      </span>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="h-1 w-48 cursor-pointer appearance-none rounded bg-zinc-700 accent-emerald-500"
      />
    </label>
  );
}

function Legend() {
  const items: { rating: CellRating }[] = [
    { rating: "excellent" },
    { rating: "good" },
    { rating: "neutral" },
    { rating: "loss" },
  ];
  return (
    <div className="flex items-center gap-3">
      {items.map((i) => (
        <span key={i.rating} className="flex items-center gap-1.5">
          <span className={cls("h-3 w-3 rounded-sm", RATING_STYLE[i.rating].bg)} />
          {RATING_STYLE[i.rating].tag}
        </span>
      ))}
    </div>
  );
}
