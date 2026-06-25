"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  ReferenceArea,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  getSeasonalHeatmap,
  getSeasonalPattern,
  getSeasonalPatterns,
  getSeasonalProfile,
  getSeasonalScanStatus,
  getSeasonalUniverse,
  getSeasonalUpcoming,
  runSeasonalScan,
  type SeasonalHeatmapResponse,
  type SeasonalPattern,
  type SeasonalPatternDetailResponse,
  type SeasonalPatternsResponse,
  type SeasonalProfileResponse,
  type SeasonalStatus,
  type SeasonalUniverseItem,
} from "@/lib/api";
import Heatmap from "./Heatmap";
import IntradayView from "./IntradayView";

type Mode = "daily" | "intraday";

// ── styling helpers ──────────────────────────────────────────────────────────
const AXIS = { fill: "#71717a", fontSize: 10 };
const GRID = "#27272a";
const TOOLTIP = {
  background: "#18181b",
  border: "1px solid #3f3f46",
  borderRadius: 8,
  fontSize: 12,
  color: "#e4e4e7",
};

const STATUS: Record<SeasonalStatus, { label: string; cls: string; dot: string }> = {
  active: { label: "AKTIV", cls: "bg-emerald-950/60 text-emerald-300 border-emerald-800/60", dot: "bg-emerald-400" },
  weak: { label: "SCHWACH", cls: "bg-amber-950/60 text-amber-300 border-amber-800/60", dot: "bg-amber-400" },
  decayed: { label: "VERFLOGEN", cls: "bg-red-950/60 text-red-300 border-red-800/60", dot: "bg-red-400" },
};
const CLASS_LABEL: Record<string, string> = {
  commodity: "Rohstoffe", index: "Indizes", equity: "Aktien", crypto: "Krypto", other: "Sonstige",
};

const pct = (x: number, d = 2) => `${x >= 0 ? "+" : ""}${(x * 100).toFixed(d)}%`;
const num = (x: number | null | undefined, d = 2) => (x == null || Number.isNaN(x) ? "–" : x.toFixed(d));
const mdLabel = (md: [number, number]) => {
  const m = ["Jan", "Feb", "Mär", "Apr", "Mai", "Jun", "Jul", "Aug", "Sep", "Okt", "Nov", "Dez"];
  return `${String(md[1]).padStart(2, "0")} ${m[md[0] - 1]}`;
};
const dirArrow = (d: string) => (d === "long" ? "▲" : "▼");
const dirCls = (d: string) => (d === "long" ? "text-emerald-400" : "text-red-400");

type UpcomingSort = "soon" | "winrate" | "sharpe";

export default function SeasonalPage() {
  const [mode, setMode] = useState<Mode>("daily");
  const [universe, setUniverse] = useState<SeasonalUniverseItem[]>([]);
  const [ticker, setTicker] = useState<string>("GC=F");
  const [profile, setProfile] = useState<SeasonalProfileResponse | null>(null);
  const [heatmap, setHeatmap] = useState<SeasonalHeatmapResponse | null>(null);
  const [patterns, setPatterns] = useState<SeasonalPatternsResponse | null>(null);
  const [detail, setDetail] = useState<SeasonalPatternDetailResponse | null>(null);
  const [selected, setSelected] = useState<SeasonalPattern | null>(null);

  const [upcoming, setUpcoming] = useState<SeasonalPattern[]>([]);
  const [upMeta, setUpMeta] = useState<{ exists: boolean; built_at?: string; asof?: string } | null>(null);
  const [horizon, setHorizon] = useState(30);
  const [upSort, setUpSort] = useState<UpcomingSort>("soon");

  const [loading, setLoading] = useState(false);
  const [scanning, setScanning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // initial: universe + upcoming
  useEffect(() => {
    getSeasonalUniverse().then((d) => d.ok && setUniverse(d.universe)).catch(() => {});
  }, []);

  const loadUpcoming = useCallback(() => {
    getSeasonalUpcoming(horizon, 40)
      .then((d) => {
        if (!d.ok) return;
        setUpcoming(d.patterns);
        setUpMeta({ exists: d.exists ?? false, built_at: d.built_at, asof: d.asof });
      })
      .catch(() => {});
  }, [horizon]);
  useEffect(loadUpcoming, [loadUpcoming]);

  // selected ticker → profile + heatmap + patterns
  useEffect(() => {
    if (!ticker) return;
    setLoading(true);
    setError(null);
    setSelected(null);
    setDetail(null);
    Promise.all([
      getSeasonalProfile(ticker),
      getSeasonalHeatmap(ticker),
      getSeasonalPatterns(ticker, { top: 12 }),
    ])
      .then(([p, h, pat]) => {
        if (!p.ok) throw new Error(p.error || "profile failed");
        setProfile(p);
        setHeatmap(h.ok ? h : null);
        setPatterns(pat.ok ? pat : null);
      })
      .catch((e) => setError(String(e.message || e)))
      .finally(() => setLoading(false));
  }, [ticker]);

  const selectPattern = useCallback(
    (p: SeasonalPattern) => {
      setSelected(p);
      setDetail(null);
      getSeasonalPattern(p.ticker, mdParam(p.start_md), mdParam(p.end_md), p.direction)
        .then((d) => d.ok && setDetail(d))
        .catch(() => {});
    },
    [],
  );

  const rebuild = useCallback(() => {
    setScanning(true);
    runSeasonalScan()
      .then(() => {
        // poll the background scan until it finishes, then refresh upcoming
        const poll = setInterval(async () => {
          try {
            const s = await getSeasonalScanStatus();
            if (!s.running) {
              clearInterval(poll);
              setScanning(false);
              loadUpcoming();
            }
          } catch {
            clearInterval(poll);
            setScanning(false);
          }
        }, 3000);
      })
      .catch(() => setScanning(false));
  }, [loadUpcoming]);

  const groups = useMemo(() => {
    const g: Record<string, SeasonalUniverseItem[]> = {};
    for (const u of universe) (g[u.asset_class] ??= []).push(u);
    return g;
  }, [universe]);

  const upSorted = useMemo(() => {
    const arr = [...upcoming];
    if (upSort === "winrate") arr.sort((a, b) => b.win_rate - a.win_rate);
    else if (upSort === "sharpe") arr.sort((a, b) => (b.sharpe || 0) - (a.sharpe || 0));
    else arr.sort((a, b) => (a.days_until_start ?? 99) - (b.days_until_start ?? 99));
    return arr;
  }, [upcoming, upSort]);

  // map a (month,day) to the curve's day-of-year index for the highlight band
  const doyOf = useCallback(
    (md: [number, number]): number | null => {
      if (!profile) return null;
      const lab = `${String(md[1]).padStart(2, "0")} ${["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"][md[0] - 1]}`;
      const hit = profile.curve.find((c) => c.label === lab);
      if (hit) return hit.doy;
      // fall back to the first point in that month
      const m = profile.curve.find((c) => c.label.endsWith(["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"][md[0] - 1]));
      return m?.doy ?? null;
    },
    [profile],
  );

  const band = useMemo(() => {
    if (!selected) return null;
    const s = doyOf(selected.start_md);
    const e = doyOf(selected.end_md);
    if (s == null || e == null) return null;
    return e >= s ? { x1: s, x2: e } : { x1: s, x2: profile?.curve.length ?? 365 };
  }, [selected, doyOf, profile]);

  const monthTicks = useMemo(() => {
    if (!profile) return [];
    const seen = new Set<string>();
    const ticks: number[] = [];
    for (const c of profile.curve) {
      const mon = c.label.slice(3);
      if (!seen.has(mon)) {
        seen.add(mon);
        ticks.push(c.doy);
      }
    }
    return ticks;
  }, [profile]);

  return (
    <main className="mx-auto max-w-6xl px-8 py-8">
      <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Seasonal Calendar</h1>
          <p className="mt-1 text-sm text-zinc-400">
            Saisonale Muster über Assetklassen — entdeckt, statistisch validiert und auf Alpha-Decay
            geprüft.
          </p>
          <div className="mt-3 inline-flex overflow-hidden rounded-lg border border-zinc-700 text-sm">
            {(["daily", "intraday"] as Mode[]).map((m) => (
              <button
                key={m}
                onClick={() => setMode(m)}
                className={`px-4 py-1.5 font-medium transition ${
                  mode === m ? "bg-zinc-700 text-zinc-100" : "bg-zinc-900 text-zinc-400 hover:text-zinc-200"
                }`}
              >
                {m === "daily" ? "Täglich (Kalender)" : "Intraday"}
              </button>
            ))}
          </div>
        </div>
        {mode === "daily" && (
          <div className="text-right text-xs text-zinc-500">
            {upMeta?.built_at && <div>Snapshot: {fmtDate(upMeta.built_at)}</div>}
            <button
              onClick={rebuild}
              disabled={scanning}
              className="mt-1 rounded-md border border-zinc-700 bg-zinc-900 px-3 py-1.5 text-xs font-medium text-zinc-200 hover:bg-zinc-800 disabled:opacity-50"
            >
              {scanning ? "Scanne … (läuft im Hintergrund)" : "Snapshot neu bauen"}
            </button>
          </div>
        )}
      </div>

      {mode === "intraday" && <IntradayView />}

      {mode === "daily" && (
      <>
      {/* ── Top Upcoming Patterns ─────────────────────────────────────────── */}
      <section className="mb-8 rounded-xl border border-zinc-800 bg-zinc-900/40 p-5">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-zinc-300">
            Top Upcoming Patterns
          </h2>
          <div className="flex items-center gap-3 text-xs">
            <label className="flex items-center gap-1.5 text-zinc-400">
              Horizont
              <select
                value={horizon}
                onChange={(e) => setHorizon(Number(e.target.value))}
                className="rounded border border-zinc-700 bg-zinc-900 px-2 py-1 text-zinc-200"
              >
                {[14, 30, 60, 90].map((h) => (
                  <option key={h} value={h}>{h} Tage</option>
                ))}
              </select>
            </label>
            <div className="flex overflow-hidden rounded border border-zinc-700">
              {(["soon", "winrate", "sharpe"] as UpcomingSort[]).map((s) => (
                <button
                  key={s}
                  onClick={() => setUpSort(s)}
                  className={`px-2.5 py-1 ${upSort === s ? "bg-zinc-700 text-zinc-100" : "bg-zinc-900 text-zinc-400 hover:text-zinc-200"}`}
                >
                  {s === "soon" ? "Start" : s === "winrate" ? "Trefferquote" : "Sharpe"}
                </button>
              ))}
            </div>
          </div>
        </div>

        {!upMeta?.exists ? (
          <p className="text-sm text-zinc-500">
            Noch kein Snapshot. Klicke „Snapshot neu bauen", um das Universum zu scannen.
          </p>
        ) : upSorted.length === 0 ? (
          <p className="text-sm text-zinc-500">Keine Muster starten in den nächsten {horizon} Tagen.</p>
        ) : (
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3">
            {upSorted.slice(0, 12).map((p, i) => (
              <button
                key={`${p.ticker}-${i}`}
                onClick={() => setTicker(p.ticker)}
                className="group flex flex-col gap-1.5 rounded-lg border border-zinc-800 bg-zinc-950/60 p-3 text-left transition hover:border-zinc-600"
              >
                <div className="flex items-center justify-between">
                  <span className="text-sm font-semibold text-zinc-100">{p.name}</span>
                  <span className={`rounded border px-1.5 py-0.5 text-[10px] font-medium ${STATUS[p.status].cls}`}>
                    {STATUS[p.status].label}
                  </span>
                </div>
                <div className="flex items-center gap-2 text-xs text-zinc-400">
                  <span className={`font-semibold ${dirCls(p.direction)}`}>{dirArrow(p.direction)} {p.direction === "long" ? "Long" : "Short"}</span>
                  <span className="text-zinc-500">{mdLabel(p.start_md)} – {mdLabel(p.end_md)}</span>
                </div>
                <div className="flex items-center justify-between text-xs">
                  <span className="text-amber-400">
                    {p.days_until_start === 0 ? "startet heute" : `in ${p.days_until_start} Tg.`}
                  </span>
                  <span className="font-mono text-zinc-300">
                    {pct(p.mean_return)} · WR {(p.win_rate * 100).toFixed(0)}% · Sh {num(p.sharpe)}
                  </span>
                </div>
              </button>
            ))}
          </div>
        )}
      </section>

      {/* ── Ticker selector ───────────────────────────────────────────────── */}
      <div className="mb-6 space-y-2">
        {Object.entries(groups).map(([cls, items]) => (
          <div key={cls} className="flex items-start gap-3">
            <span className="w-20 shrink-0 pt-1.5 text-[11px] uppercase tracking-wide text-zinc-500">{CLASS_LABEL[cls] ?? cls}</span>
            <div className="flex flex-1 flex-wrap gap-1.5">
              {items.map((u) => (
                <button
                  key={u.ticker}
                  onClick={() => setTicker(u.ticker)}
                  className={`rounded-md border px-2.5 py-1 text-xs font-medium transition ${
                    ticker === u.ticker
                      ? "border-sky-600 bg-sky-950/60 text-sky-200"
                      : "border-zinc-800 bg-zinc-900/50 text-zinc-400 hover:border-zinc-600 hover:text-zinc-200"
                  }`}
                  title={u.note}
                >
                  {u.name}
                </button>
              ))}
            </div>
          </div>
        ))}
      </div>

      {error && (
        <div className="mb-6 rounded-lg border border-red-900 bg-red-950/40 px-4 py-3 text-sm text-red-300">
          {error}
        </div>
      )}

      {profile && (
        <>
          {/* asset header */}
          <div className="mb-4 flex flex-wrap items-baseline justify-between gap-2">
            <h2 className="text-xl font-semibold">
              {profile.meta.name}{" "}
              <span className="font-mono text-sm text-zinc-500">{profile.ticker}</span>
            </h2>
            <span className="text-xs text-zinc-500">
              {profile.span.start} – {profile.span.end} · {profile.span.n_years} Jahre
            </span>
          </div>
          {profile.meta.note && (
            <p className="mb-5 max-w-3xl text-sm text-zinc-400">{profile.meta.note}</p>
          )}

          {/* ── Seasonal equity curve ─────────────────────────────────────── */}
          <section className="mb-6 rounded-xl border border-zinc-800 bg-zinc-900/40 p-5">
            <div className="mb-3 flex items-center justify-between">
              <h3 className="text-sm font-semibold text-zinc-200">Saisonaler Verlauf (Durchschnittsjahr)</h3>
              {selected && (
                <span className="text-xs text-zinc-400">
                  Fenster: <span className="text-zinc-200">{selected.window_label}</span>{" "}
                  <span className={dirCls(selected.direction)}>{dirArrow(selected.direction)}</span>
                </span>
              )}
            </div>
            <ResponsiveContainer width="100%" height={280}>
              <AreaChart data={profile.curve} margin={{ top: 5, right: 10, left: -10, bottom: 0 }}>
                <defs>
                  <linearGradient id="szFill" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#38bdf8" stopOpacity={0.35} />
                    <stop offset="100%" stopColor="#38bdf8" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
                <XAxis
                  dataKey="doy"
                  ticks={monthTicks}
                  tickFormatter={(d) => profile.curve[d - 1]?.label.slice(3) ?? ""}
                  tick={AXIS}
                />
                <YAxis tick={AXIS} width={48} tickFormatter={(v) => `${v}%`} />
                <Tooltip
                  contentStyle={TOOLTIP}
                  labelFormatter={(d) => profile.curve[Number(d) - 1]?.label ?? ""}
                  formatter={(v) => [`${Number(v) >= 0 ? "+" : ""}${Number(v).toFixed(2)}%`, "Ø kumuliert"]}
                />
                <ReferenceLine y={0} stroke="#52525b" />
                {band && (
                  <ReferenceArea x1={band.x1} x2={band.x2} fill="#f59e0b" fillOpacity={0.12} stroke="#f59e0b" strokeOpacity={0.3} />
                )}
                <Area type="monotone" dataKey="cum_return" stroke="#38bdf8" strokeWidth={2} fill="url(#szFill)" isAnimationActive={false} />
              </AreaChart>
            </ResponsiveContainer>
            <p className="mt-1 text-[11px] text-zinc-500">
              Kumulierte durchschnittliche Tagesrendite über das standardisierte Jahr (alle {profile.span.n_years}{" "}
              Jahre gemittelt, Start = 0%). Ein Muster anklicken hebt sein Fenster hervor.
            </p>
          </section>

          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            {/* ── Monthly bars ────────────────────────────────────────────── */}
            <section className="rounded-xl border border-zinc-800 bg-zinc-900/40 p-5">
              <h3 className="mb-3 text-sm font-semibold text-zinc-200">Monatliche Ø-Performance</h3>
              <ResponsiveContainer width="100%" height={220}>
                <BarChart data={profile.monthly}>
                  <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
                  <XAxis dataKey="month" tick={AXIS} />
                  <YAxis tick={AXIS} width={40} tickFormatter={(v) => `${v}%`} />
                  <Tooltip
                    contentStyle={TOOLTIP}
                    formatter={(v, _n, item) => {
                      const pl = (item?.payload ?? {}) as { hit_rate?: number; p_value?: number };
                      return [
                        `${Number(v) >= 0 ? "+" : ""}${Number(v).toFixed(2)}%  (WR ${((pl.hit_rate ?? 0) * 100).toFixed(0)}%, p=${(pl.p_value ?? 1).toFixed(2)})`,
                        "Ø Monat",
                      ];
                    }}
                  />
                  <ReferenceLine y={0} stroke="#52525b" />
                  <Bar dataKey="mean_return" isAnimationActive={false} radius={[2, 2, 0, 0]}>
                    {profile.monthly.map((m, i) => (
                      <Cell key={i} fill={m.mean_return >= 0 ? "#10b981" : "#ef4444"} fillOpacity={m.p_value < 0.05 ? 0.95 : 0.45} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
              <p className="mt-1 text-[11px] text-zinc-500">
                Volle Sättigung = statistisch signifikant (p &lt; 0,05).
              </p>
            </section>

            {/* ── Selected pattern detail ─────────────────────────────────── */}
            <section className="rounded-xl border border-zinc-800 bg-zinc-900/40 p-5">
              <h3 className="mb-3 text-sm font-semibold text-zinc-200">
                {selected ? `Muster: ${selected.window_label}` : "Muster-Detail"}
              </h3>
              {!selected ? (
                <p className="py-12 text-center text-sm text-zinc-500">
                  Wähle unten ein Muster aus der Tabelle.
                </p>
              ) : (
                <>
                  <div className="mb-3 grid grid-cols-3 gap-3 text-center">
                    <Stat label="Ø Rendite" value={pct(selected.mean_return)} good={selected.mean_return > 0} />
                    <Stat label="Trefferquote" value={`${(selected.win_rate * 100).toFixed(0)}%`} good={selected.win_rate >= 0.5} />
                    <Stat label="Sharpe" value={num(selected.sharpe)} good={selected.sharpe > 0} />
                    <Stat label="p-Value" value={num(selected.p_value, 3)} good={selected.p_value < 0.05} />
                    <Stat label="Jahre" value={String(selected.n_years)} />
                    <Stat label="Status" value={STATUS[selected.status].label}
                      cls={STATUS[selected.status].cls.replace("border-", "text-").split(" ").find((c) => c.startsWith("text-")) ?? ""} />
                  </div>
                  {detail && detail.path.length > 0 && (
                    <ResponsiveContainer width="100%" height={130}>
                      <LineChart data={detail.path} margin={{ top: 4, right: 6, left: -18, bottom: 0 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
                        <XAxis dataKey="t" tick={AXIS} tickFormatter={(t) => `T${t}`} />
                        <YAxis tick={AXIS} width={42} domain={["auto", "auto"]} />
                        <Tooltip contentStyle={TOOLTIP} formatter={(v) => [Number(v).toFixed(2), "Ø Index (Entry=100)"]} labelFormatter={(t) => `Handelstag ${t}`} />
                        <ReferenceLine y={100} stroke="#52525b" strokeDasharray="2 2" />
                        <Line type="monotone" dataKey="value" stroke="#f59e0b" strokeWidth={2} dot={false} isAnimationActive={false} />
                      </LineChart>
                    </ResponsiveContainer>
                  )}
                  {selected.recent_p_value != null && (
                    <p className="mt-2 text-[11px] text-zinc-500">
                      Alpha-Decay: letzte {selected.recent_years} Jahre Ø {pct(selected.recent_mean ?? 0)},
                      WR {((selected.recent_win_rate ?? 0) * 100).toFixed(0)}%, p={num(selected.recent_p_value, 3)}.{" "}
                      {selected.status === "active"
                        ? "Weiterhin signifikant."
                        : selected.status === "weak"
                          ? "Zuletzt nicht mehr signifikant — Vorsicht."
                          : "Edge verflogen / Vorzeichen gedreht."}
                    </p>
                  )}
                </>
              )}
            </section>
          </div>

          {/* ── Heatmap ───────────────────────────────────────────────────── */}
          {heatmap && (
            <section className="mt-6 rounded-xl border border-zinc-800 bg-zinc-900/40 p-5">
              <h3 className="mb-3 text-sm font-semibold text-zinc-200">Performance-Heatmap (Monat × Jahr)</h3>
              <Heatmap data={heatmap} />
            </section>
          )}

          {/* ── Patterns table ────────────────────────────────────────────── */}
          {patterns && patterns.patterns.length > 0 && (
            <section className="mt-6 rounded-xl border border-zinc-800 bg-zinc-900/40 p-5">
              <div className="mb-3 flex items-center justify-between">
                <h3 className="text-sm font-semibold text-zinc-200">Stärkste Muster</h3>
                <span className="text-[11px] text-zinc-500">{patterns.n_scanned} Fenster gescannt</span>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="text-left text-[11px] uppercase tracking-wide text-zinc-500">
                    <tr className="border-b border-zinc-800">
                      <th className="py-2 pr-3">Richtung</th>
                      <th className="py-2 pr-3">Fenster</th>
                      <th className="py-2 pr-3 text-right">Ø Rendite</th>
                      <th className="py-2 pr-3 text-right">Median</th>
                      <th className="py-2 pr-3 text-right">Trefferq.</th>
                      <th className="py-2 pr-3 text-right">Sharpe</th>
                      <th className="py-2 pr-3 text-right">p-Value</th>
                      <th className="py-2 pr-3 text-right">Tage</th>
                      <th className="py-2 pr-3">Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {patterns.patterns.map((p, i) => (
                      <tr
                        key={i}
                        onClick={() => selectPattern(p)}
                        className={`cursor-pointer border-b border-zinc-900 transition hover:bg-zinc-800/40 ${
                          selected?.window_label === p.window_label && selected?.direction === p.direction ? "bg-zinc-800/60" : ""
                        }`}
                      >
                        <td className={`py-2 pr-3 font-semibold ${dirCls(p.direction)}`}>{dirArrow(p.direction)} {p.direction === "long" ? "Long" : "Short"}</td>
                        <td className="py-2 pr-3 text-zinc-200">{p.window_label}</td>
                        <td className={`py-2 pr-3 text-right font-mono tabular-nums ${p.mean_return >= 0 ? "text-emerald-400" : "text-red-400"}`}>{pct(p.mean_return)}</td>
                        <td className="py-2 pr-3 text-right font-mono tabular-nums text-zinc-400">{pct(p.median_return)}</td>
                        <td className="py-2 pr-3 text-right font-mono tabular-nums text-zinc-300">{(p.win_rate * 100).toFixed(0)}%</td>
                        <td className="py-2 pr-3 text-right font-mono tabular-nums text-zinc-300">{num(p.sharpe)}</td>
                        <td className={`py-2 pr-3 text-right font-mono tabular-nums ${p.p_value < 0.05 ? "text-emerald-400" : "text-zinc-500"}`}>{num(p.p_value, 3)}</td>
                        <td className="py-2 pr-3 text-right font-mono tabular-nums text-zinc-500">{p.calendar_days}</td>
                        <td className="py-2 pr-3">
                          <span className={`inline-flex items-center gap-1 rounded border px-1.5 py-0.5 text-[10px] font-medium ${STATUS[p.status].cls}`}>
                            <span className={`h-1.5 w-1.5 rounded-full ${STATUS[p.status].dot}`} />
                            {STATUS[p.status].label}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <p className="mt-2 text-[11px] text-zinc-500">
                Aus {patterns.n_scanned} gescannten Fenstern (Mehrfachtest-Hinweis: ein hoher Score ist ein
                Kandidat, kein Beweis — Decay-Status und ökonomische Begründung beachten).
              </p>
            </section>
          )}
        </>
      )}

      {loading && !profile && <p className="text-sm text-zinc-500">Lade …</p>}
      </>
      )}
    </main>
  );
}

// ── small components / helpers ───────────────────────────────────────────────
function Stat({ label, value, good, cls }: { label: string; value: string; good?: boolean; cls?: string }) {
  const color = cls ?? (good == null ? "text-zinc-200" : good ? "text-emerald-400" : "text-red-400");
  return (
    <div className="rounded-lg bg-zinc-950/60 px-2 py-2">
      <div className="text-[10px] uppercase tracking-wide text-zinc-500">{label}</div>
      <div className={`mt-0.5 font-mono text-sm font-semibold ${color}`}>{value}</div>
    </div>
  );
}

const mdParam = (md: [number, number]) => `${String(md[0]).padStart(2, "0")}-${String(md[1]).padStart(2, "0")}`;
const fmtDate = (iso: string) =>
  new Date(iso).toLocaleString("de-DE", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });
