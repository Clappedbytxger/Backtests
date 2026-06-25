"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  getAltAnomalies,
  getAltEvents,
  getAltSeries,
  getAltSources,
  getAltStatus,
  ingestAltData,
  seedAltData,
  type AltAnomalyPoint,
  type AltEvent,
  type AltSeriesResponse,
  type AltSource,
} from "@/lib/api";

const cls = (...x: (string | false | undefined)[]) => x.filter(Boolean).join(" ");
const pct = (v: number | null | undefined, d = 1) =>
  v == null || !isFinite(v) ? "—" : `${v >= 0 ? "+" : ""}${(v * 100).toFixed(d)}%`;

const SEV: Record<string, { dot: string; text: string; border: string }> = {
  alert: { dot: "bg-red-500", text: "text-red-300", border: "border-red-700/50" },
  warn: { dot: "bg-amber-400", text: "text-amber-300", border: "border-amber-700/40" },
  info: { dot: "bg-sky-400", text: "text-sky-300", border: "border-zinc-800" },
};

export default function AltDataPage() {
  const [sources, setSources] = useState<AltSource[]>([]);
  const [events, setEvents] = useState<AltEvent[]>([]);
  const [anomalies, setAnomalies] = useState<AltAnomalyPoint[]>([]);
  const [ticker, setTicker] = useState("BTC-USD");
  const [series, setSeries] = useState<AltSeriesResponse | null>(null);
  const [empty, setEmpty] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const loadOverview = useCallback(() => {
    Promise.all([getAltEvents(40), getAltAnomalies(), getAltStatus()])
      .then(([ev, an, st]) => {
        setEvents(ev.events ?? []);
        setAnomalies(an.points ?? []);
        setEmpty((st.store?.n_events ?? 0) === 0 && (st.store?.n_repos_tracked ?? 0) === 0);
      })
      .catch((e) => setError(String(e)));
  }, []);

  useEffect(() => {
    getAltSources().then((r) => setSources(r.sources)).catch(() => {});
    loadOverview();
  }, [loadOverview]);

  useEffect(() => {
    getAltSeries(ticker, 3).then(setSeries).catch((e) => setError(String(e)));
  }, [ticker]);

  const onSeed = async () => {
    setBusy("seed");
    setError(null);
    try {
      await seedAltData();
      loadOverview();
      setSeries(await getAltSeries(ticker, 3));
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(null);
    }
  };

  const onIngest = async () => {
    setBusy("ingest");
    setError(null);
    try {
      await ingestAltData();
      // poll status until the background job finishes
      const poll = setInterval(async () => {
        const st = await getAltStatus();
        if (st.job?.status !== "running") {
          clearInterval(poll);
          loadOverview();
          setBusy(null);
        }
      }, 2000);
    } catch (e) {
      setError(String(e));
      setBusy(null);
    }
  };

  return (
    <main className="mx-auto max-w-7xl px-8 py-8">
      <header className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">Alternative Insights Desk</h1>
          <p className="mt-1 max-w-2xl text-sm text-zinc-400">
            Unstrukturierte Datenströme — GitHub-Entwickleraktivität und SEC-10-K/10-Q-Filings —
            aggregiert, mit lokaler NLP strukturiert (Lexikon-Sentiment, TF-IDF-Divergenz) und auf
            eine tägliche Zeitskala mit Preisdaten gematcht.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={onIngest}
            disabled={!!busy}
            className="rounded-md border border-emerald-700/60 bg-emerald-600/15 px-3 py-1.5 text-xs font-medium text-emerald-300 hover:bg-emerald-600/25 disabled:opacity-50"
          >
            {busy === "ingest" ? "Scrape läuft …" : "Live-Ingest starten"}
          </button>
          <button
            onClick={onSeed}
            disabled={!!busy}
            className="rounded-md border border-zinc-700 bg-zinc-800/50 px-3 py-1.5 text-xs font-medium text-zinc-300 hover:bg-zinc-700/50 disabled:opacity-50"
          >
            {busy === "seed" ? "…" : "Demo-Daten laden"}
          </button>
        </div>
      </header>

      {error && (
        <div className="mb-6 rounded-lg border border-red-700/60 bg-red-950/40 px-4 py-3 text-sm text-red-300">
          {error}
        </div>
      )}
      {empty && (
        <div className="mb-6 rounded-lg border border-amber-700/50 bg-amber-950/30 px-4 py-3 text-sm text-amber-200">
          Noch keine Alt-Daten gespeichert. Starte einen Live-Ingest (benötigt Netzzugang) oder lade
          die Demo-Daten, um das Desk zu befüllen.
        </div>
      )}

      {/* top row: ticker feed + anomaly radar */}
      <div className="mb-6 grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.2fr)]">
        <AltTicker events={events} />
        <AnomalyRadar points={anomalies} onPick={setTicker} active={ticker} />
      </div>

      {/* sentiment vs price */}
      <SentimentPrice
        series={series}
        ticker={ticker}
        sources={sources}
        onTicker={setTicker}
      />
    </main>
  );
}

// ── Alt-Data Ticker (live event feed) ────────────────────────────────────────
function AltTicker({ events }: { events: AltEvent[] }) {
  return (
    <section className="flex flex-col rounded-xl border border-zinc-800 bg-zinc-900/40">
      <div className="flex items-center gap-2 border-b border-zinc-800 px-5 py-3">
        <span className="relative flex h-2 w-2">
          <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75" />
          <span className="relative inline-flex h-2 w-2 rounded-full bg-emerald-400" />
        </span>
        <h2 className="text-sm font-semibold">Alt-Data Ticker</h2>
        <span className="ml-auto text-[10px] uppercase tracking-widest text-zinc-600">
          {events.length} Events
        </span>
      </div>
      <ul className="max-h-[340px] divide-y divide-zinc-900 overflow-y-auto">
        {events.length === 0 && (
          <li className="px-5 py-8 text-center text-sm text-zinc-600">Keine Events.</li>
        )}
        {events.map((e, i) => {
          const sv = SEV[e.severity] ?? SEV.info;
          const inner = (
            <div className="flex items-start gap-3 px-5 py-2.5 transition-colors hover:bg-zinc-900/50">
              <span className={cls("mt-1.5 h-2 w-2 shrink-0 rounded-full", sv.dot)} />
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <span className="font-mono text-[10px] text-zinc-500">{e.ticker}</span>
                  <span className="text-[10px] text-zinc-600">
                    {new Date(e.ts).toLocaleString("de-DE", { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}
                  </span>
                </div>
                <div className={cls("text-sm", sv.text)}>{e.title}</div>
              </div>
            </div>
          );
          return (
            <li key={i}>
              {e.url ? (
                <a href={e.url} target="_blank" rel="noopener noreferrer">
                  {inner}
                </a>
              ) : (
                inner
              )}
            </li>
          );
        })}
      </ul>
    </section>
  );
}

// ── Anomaly Radar (scatter / bubble) ─────────────────────────────────────────
function AnomalyRadar({
  points,
  onPick,
  active,
}: {
  points: AltAnomalyPoint[];
  onPick: (t: string) => void;
  active: string;
}) {
  const W = 560;
  const H = 360;
  const pad = { l: 48, r: 20, t: 24, b: 40 };
  const xDom = 8; // z clamped to ±8
  const yDom = useMemo(
    () => Math.max(0.06, ...points.map((p) => Math.abs(p.price_ret_5d ?? 0))),
    [points],
  );
  const sx = (z: number) => pad.l + ((z + xDom) / (2 * xDom)) * (W - pad.l - pad.r);
  const sy = (r: number) => pad.t + ((yDom - r) / (2 * yDom)) * (H - pad.t - pad.b);

  return (
    <section className="rounded-xl border border-zinc-800 bg-zinc-900/40">
      <div className="flex items-center gap-2 border-b border-zinc-800 px-5 py-3">
        <h2 className="text-sm font-semibold">Anomalie-Radar</h2>
        <span className="ml-auto text-[10px] uppercase tracking-widest text-zinc-600">
          Alt-Data-Ausschlag (z) vs. 5-Tage-Kurs
        </span>
      </div>
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full">
        {/* quadrant grid */}
        <line x1={sx(0)} y1={pad.t} x2={sx(0)} y2={H - pad.b} stroke="#3f3f46" strokeDasharray="3 3" />
        <line x1={pad.l} y1={sy(0)} x2={W - pad.r} y2={sy(0)} stroke="#3f3f46" strokeDasharray="3 3" />
        {/* anomaly band |z|>=3 */}
        <rect x={sx(3)} y={pad.t} width={W - pad.r - sx(3)} height={H - pad.t - pad.b} fill="#22c55e08" />
        <rect x={pad.l} y={pad.t} width={sx(-3) - pad.l} height={H - pad.t - pad.b} fill="#ef444408" />
        {/* axis labels */}
        <text x={W - pad.r} y={sy(0) - 6} textAnchor="end" className="fill-zinc-600 text-[10px]">
          z →
        </text>
        <text x={sx(0) + 6} y={pad.t + 10} className="fill-zinc-600 text-[10px]">
          Kurs ↑
        </text>
        {points.map((p) => {
          const z = p.z ?? 0;
          const y = p.price_ret_5d ?? 0;
          const r = 6 + (p.size ?? 0) * 3.2;
          const hot = Math.abs(z) >= 3;
          const isActive = p.ticker === active;
          const color = p.asset_class === "crypto" ? "#a78bfa" : "#38bdf8";
          return (
            <g key={p.ticker} className="cursor-pointer" onClick={() => onPick(p.ticker)}>
              <circle
                cx={sx(z)}
                cy={sy(y)}
                r={r}
                fill={color}
                fillOpacity={hot ? 0.5 : 0.22}
                stroke={isActive ? "#fff" : color}
                strokeWidth={isActive ? 2 : 1}
              >
                <title>{`${p.name} — z ${z.toFixed(1)} · 5T ${pct(y)} · ${p.detail}`}</title>
              </circle>
              <text
                x={sx(z)}
                y={sy(y) - r - 3}
                textAnchor="middle"
                className={cls("text-[9px]", hot ? "fill-zinc-200" : "fill-zinc-500")}
              >
                {p.ticker}
              </text>
            </g>
          );
        })}
      </svg>
      <div className="flex items-center gap-4 px-5 pb-3 text-[10px] text-zinc-500">
        <span className="flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-full bg-sky-400/40" />Equity</span>
        <span className="flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-full bg-violet-400/40" />Crypto</span>
        <span className="ml-auto">Blasengröße = |z| · grüne Zone = positiver Ausschlag</span>
      </div>
    </section>
  );
}

// ── Sentiment / commit score vs price (dual-axis) ────────────────────────────
function SentimentPrice({
  series,
  ticker,
  sources,
  onTicker,
}: {
  series: AltSeriesResponse | null;
  ticker: string;
  sources: AltSource[];
  onTicker: (t: string) => void;
}) {
  const W = 1080;
  const H = 320;
  const pad = { l: 56, r: 56, t: 24, b: 28 };

  const chart = useMemo(() => {
    if (!series || !series.ok || series.price.length === 0) return null;
    const price = series.price.filter((p) => p.close != null) as { t: string; close: number }[];
    const score = series.score.filter((p) => p.value != null) as { t: string; value: number; z: number | null }[];
    if (price.length === 0) return null;
    const idx = new Map(price.map((p, i) => [p.t, i]));
    const n = price.length;
    const xi = (i: number) => pad.l + (i / Math.max(1, n - 1)) * (W - pad.l - pad.r);
    const pMin = Math.min(...price.map((p) => p.close));
    const pMax = Math.max(...price.map((p) => p.close));
    const yP = (v: number) => pad.t + (1 - (v - pMin) / Math.max(1e-9, pMax - pMin)) * (H - pad.t - pad.b);
    const sVals = score.map((p) => p.value);
    const sMin = score.length ? Math.min(...sVals) : 0;
    const sMax = score.length ? Math.max(...sVals) : 1;
    const yS = (v: number) => pad.t + (1 - (v - sMin) / Math.max(1e-9, sMax - sMin)) * (H - pad.t - pad.b);
    const priceLine = price.map((p, i) => `${i === 0 ? "M" : "L"}${xi(i)},${yP(p.close)}`).join(" ");
    const scoreLine = score
      .map((p) => {
        const i = idx.get(p.t);
        return i == null ? null : `${xi(i)},${yS(p.value)}`;
      })
      .filter(Boolean)
      .map((c, i) => `${i === 0 ? "M" : "L"}${c}`)
      .join(" ");
    const markers = series.filings
      .map((f) => {
        const i = idx.get(f.t);
        return i == null ? null : { x: xi(i), ...f };
      })
      .filter(Boolean) as { x: number; t: string; label: string; divergence: number | null; sentiment: number | null }[];
    return { priceLine, scoreLine, markers, pMin, pMax, sMin, sMax, xi, yS };
  }, [series]);

  const scoreColor = series?.score_kind === "commits" ? "#f59e0b" : "#22c55e";
  const scoreLabel = series?.score_kind === "commits" ? "Commits/Tag (7T)" : "Sentiment";

  return (
    <section className="rounded-xl border border-zinc-800 bg-zinc-900/40">
      <div className="flex flex-wrap items-center gap-3 border-b border-zinc-800 px-5 py-3">
        <h2 className="text-sm font-semibold">Sentiment / Aktivität vs. Preis</h2>
        <select
          value={ticker}
          onChange={(e) => onTicker(e.target.value)}
          className="rounded border border-zinc-700 bg-zinc-900 px-2 py-1 text-xs text-zinc-100"
        >
          {sources.map((s) => (
            <option key={s.ticker} value={s.ticker}>
              {s.ticker} · {s.name}
            </option>
          ))}
        </select>
        <div className="ml-auto flex items-center gap-4 text-[11px]">
          <span className="flex items-center gap-1.5 text-zinc-400">
            <span className="h-0.5 w-4 bg-zinc-300" /> Preis
          </span>
          {series?.score_kind && (
            <span className="flex items-center gap-1.5" style={{ color: scoreColor }}>
              <span className="h-0.5 w-4" style={{ background: scoreColor }} /> {scoreLabel}
            </span>
          )}
          <span className="flex items-center gap-1.5 text-amber-300/80">
            <span className="h-3 w-px bg-amber-400" /> Filing
          </span>
        </div>
      </div>
      {!chart ? (
        <div className="py-20 text-center text-sm text-zinc-600">
          {series && !series.ok ? series.error : "Keine Score-Daten — Ingest oder Demo laden."}
        </div>
      ) : (
        <svg viewBox={`0 0 ${W} ${H}`} className="w-full">
          {/* filing markers */}
          {chart.markers.map((m, i) => (
            <g key={i}>
              <line x1={m.x} y1={pad.t} x2={m.x} y2={H - pad.b} stroke="#f59e0b" strokeOpacity={0.5} strokeDasharray="2 3" />
              <circle cx={m.x} cy={pad.t} r={4} fill={m.divergence != null && m.divergence >= 0.15 ? "#ef4444" : "#f59e0b"}>
                <title>{`${m.label} ${m.t}${m.divergence != null ? ` · ${(m.divergence * 100).toFixed(0)}% Textänderung` : ""}${m.sentiment != null ? ` · Sentiment ${m.sentiment.toFixed(2)}` : ""}`}</title>
              </circle>
            </g>
          ))}
          {/* score line (right axis) */}
          {chart.scoreLine && <path d={chart.scoreLine} fill="none" stroke={scoreColor} strokeWidth={1.6} strokeOpacity={0.9} />}
          {/* price line (left axis) */}
          <path d={chart.priceLine} fill="none" stroke="#e4e4e7" strokeWidth={1.6} />
          {/* y-axis labels */}
          <text x={pad.l - 8} y={pad.t + 6} textAnchor="end" className="fill-zinc-500 text-[10px]">
            {chart.pMax.toFixed(0)}
          </text>
          <text x={pad.l - 8} y={H - pad.b} textAnchor="end" className="fill-zinc-500 text-[10px]">
            {chart.pMin.toFixed(0)}
          </text>
          {series?.score_kind && (
            <>
              <text x={W - pad.r + 8} y={pad.t + 6} className="text-[10px]" style={{ fill: scoreColor }}>
                {chart.sMax.toFixed(series.score_kind === "sentiment" ? 2 : 0)}
              </text>
              <text x={W - pad.r + 8} y={H - pad.b} className="text-[10px]" style={{ fill: scoreColor }}>
                {chart.sMin.toFixed(series.score_kind === "sentiment" ? 2 : 0)}
              </text>
            </>
          )}
        </svg>
      )}
    </section>
  );
}
