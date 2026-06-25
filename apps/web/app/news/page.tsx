"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  clearNews,
  getLessons,
  getNewsDocument,
  newsFeedback,
  reevaluateNews,
  seedNews,
  tickNews,
  type Briefing,
  type HypothesisStatus,
  type ImpactDirection,
  type Lesson,
  type LlmStatus,
  type MarketSnapshot,
  type MarketTop,
  type NewsCategory,
  type NewsItem,
  type NewsPriority,
  type NewsStats,
} from "@/lib/api";

const CATEGORIES: NewsCategory[] = ["Makro", "Krypto", "Aktien", "FX", "Rohstoffe", "Sonstiges"];
const PRIORITIES: NewsPriority[] = ["High", "Medium", "Low"];

const TICK_MS = 25_000; // live-loop cadence
const REFRESH_EVERY = 6; // every Nth tick also pulls fresh RSS (~2.5 min)

// ── Bloomberg-style colour coding ────────────────────────────────────────────
const DIR_COLOR: Record<ImpactDirection, string> = {
  Bullish: "text-emerald-400",
  Bearish: "text-red-400",
  Neutral: "text-zinc-400",
};
const DIR_BG: Record<ImpactDirection, string> = {
  Bullish: "bg-emerald-950/60 text-emerald-300 border-emerald-800/60",
  Bearish: "bg-red-950/60 text-red-300 border-red-800/60",
  Neutral: "bg-zinc-800/60 text-zinc-400 border-zinc-700",
};
const PRIO_COLOR: Record<NewsPriority, string> = {
  High: "text-amber-400",
  Medium: "text-sky-400",
  Low: "text-zinc-500",
};
const PRIO_DOT: Record<NewsPriority, string> = {
  High: "bg-amber-400",
  Medium: "bg-sky-500",
  Low: "bg-zinc-600",
};
const STATUS_BADGE: Record<HypothesisStatus, { label: string; cls: string }> = {
  open: { label: "OFFEN", cls: "bg-zinc-800 text-zinc-300 border-zinc-700" },
  correct: { label: "TREFFER", cls: "bg-emerald-900/70 text-emerald-300 border-emerald-700" },
  incorrect: { label: "FEHLPROGNOSE", cls: "bg-red-900/70 text-red-300 border-red-700" },
  unverified: { label: "N/V", cls: "bg-zinc-900 text-zinc-500 border-zinc-800" },
};
const PROV: Record<string, { dot: string; text: string; label: string }> = {
  on_track: { dot: "bg-emerald-400", text: "text-emerald-400", label: "on track" },
  off_track: { dot: "bg-red-400", text: "text-red-400", label: "off track" },
  flat: { dot: "bg-zinc-500", text: "text-zinc-500", label: "flat" },
};

function fmtTime(iso: string): string {
  return new Date(iso).toLocaleString("de-DE", {
    day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit",
  });
}
const pct = (x?: number | null) => (x == null ? "–" : `${x >= 0 ? "+" : ""}${(x * 100).toFixed(2)}%`);

export default function NewsPage() {
  const [allItems, setAllItems] = useState<NewsItem[]>([]);
  const [lessons, setLessons] = useState<Lesson[]>([]);
  const [stats, setStats] = useState<NewsStats | null>(null);
  const [llm, setLlm] = useState<{ status: string; s: LlmStatus } | null>(null);
  const [market, setMarket] = useState<MarketSnapshot | null>(null);
  const [cat, setCat] = useState<NewsCategory | null>(null);
  const [prio, setPrio] = useState<NewsPriority | null>(null);
  const [statusFilter, setStatusFilter] = useState<HypothesisStatus | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [showLessons, setShowLessons] = useState(true);

  // live loop
  const [live, setLive] = useState(true);
  const [lastTick, setLastTick] = useState<Date | null>(null);
  const [ticking, setTicking] = useState(false);
  const liveRef = useRef(live);
  const tickCountRef = useRef(0);
  const runningRef = useRef(false);
  liveRef.current = live;

  const reloadLessons = useCallback(() => {
    getLessons().then((l) => setLessons(l.lessons)).catch(() => {});
  }, []);

  // one loop iteration — guarded so ticks never overlap
  const doTick = useCallback(async (forceRefresh = false) => {
    if (runningRef.current) return;
    runningRef.current = true;
    setTicking(true);
    try {
      const willRefresh = forceRefresh || tickCountRef.current % REFRESH_EVERY === 0;
      const res = await tickNews(willRefresh);
      setAllItems(res.items);
      setStats({ ok: true, ...res.summary.stats });
      setLlm({ status: res.summary.llm.status, s: res.summary.llm_status });
      setMarket(res.summary.market);
      setLastTick(new Date());
      setError(null);
      if (willRefresh || res.summary.settle.incorrect > 0) reloadLessons();
      tickCountRef.current += 1;
    } catch (e) {
      setError(String(e));
    } finally {
      runningRef.current = false;
      setTicking(false);
    }
  }, [reloadLessons]);

  // mount: prime feed + lessons, then run the interval while page is open + visible
  useEffect(() => {
    doTick(true);
    reloadLessons();
    const id = setInterval(() => {
      if (liveRef.current && !document.hidden) doTick(false);
    }, TICK_MS);
    const onVis = () => {
      if (liveRef.current && !document.hidden) doTick(false);
    };
    document.addEventListener("visibilitychange", onVis);
    return () => {
      clearInterval(id);
      document.removeEventListener("visibilitychange", onVis);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // client-side filtering over the live item set
  const items = useMemo(() => {
    return allItems.filter((it) => {
      if (cat && it.category !== cat) return false;
      if (prio && it.priority !== prio) return false;
      if (statusFilter && it.hypothesis?.status !== statusFilter) return false;
      return true;
    });
  }, [allItems, cat, prio, statusFilter]);

  const run = async (key: string, fn: () => Promise<unknown>) => {
    setBusy(key);
    setError(null);
    try {
      await fn();
      await doTick(false);
      reloadLessons();
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(null);
    }
  };

  const patchItem = (it: NewsItem) =>
    setAllItems((prev) => prev.map((p) => (p.id === it.id ? it : p)));

  const focusItem = (id: string) => {
    setExpanded(id);
    setTimeout(() => document.getElementById(`news-${id}`)?.scrollIntoView({ behavior: "smooth", block: "center" }), 60);
  };

  const onClear = async () => {
    if (!window.confirm("Feed leeren (inkl. Demo-Seeds)? Lessons bleiben erhalten. Danach werden frische echte News geladen.")) return;
    setExpanded(null);
    await run("clear", async () => {
      await clearNews(false);
      await doTick(true); // immediately repopulate with real RSS news
    });
  };

  const accuracyPct = stats?.accuracy != null ? `${(stats.accuracy * 100).toFixed(0)}%` : "–";

  return (
    <main className="mx-auto max-w-7xl px-4 py-4 font-mono text-sm">
      {/* ── ticker / stat bar ─────────────────────────────────────────────── */}
      <div className="flex flex-wrap items-center gap-x-6 gap-y-2 border-b border-amber-900/40 bg-zinc-900/60 px-4 py-2">
        <span className="text-base font-bold tracking-wider text-amber-400">QUANT-OS · NEWS TERMINAL</span>
        <button
          onClick={() => setLive((v) => !v)}
          className="flex items-center gap-1.5 text-xs"
          title="Live-Loop pausieren / fortsetzen"
        >
          <span
            className={`h-2 w-2 rounded-full ${live ? "bg-emerald-400 " + (ticking ? "animate-ping" : "animate-pulse") : "bg-zinc-600"}`}
          />
          <span className={live ? "text-emerald-400" : "text-zinc-500"}>{live ? "LIVE" : "PAUSE"}</span>
        </button>
        {lastTick && <span className="text-[10px] text-zinc-500">tick {lastTick.toLocaleTimeString("de-DE")}</span>}
        <Ticker label="ITEMS" value={stats?.n_items ?? "–"} />
        <Ticker label="OFFEN" value={stats?.n_open ?? "–"} color="text-zinc-300" />
        <Ticker label="TREFFER" value={stats?.n_correct ?? "–"} color="text-emerald-400" />
        <Ticker label="FEHL" value={stats?.n_incorrect ?? "–"} color="text-red-400" />
        <Ticker label="QUOTE" value={accuracyPct} color="text-amber-400" />
        <Ticker label="LESSONS" value={stats?.n_lessons ?? "–"} color="text-sky-400" />
        <LlmIndicator llm={llm} />
        <span className="ml-auto flex gap-2">
          <button
            onClick={() => run("refresh", () => doTick(true))}
            disabled={busy != null}
            className="rounded border border-sky-800 bg-sky-950/40 px-2.5 py-1 text-xs text-sky-300 hover:bg-sky-900/50 disabled:opacity-50"
          >
            {busy === "refresh" ? "…" : "↻ News laden"}
          </button>
          <button
            onClick={() => run("seed", seedNews)}
            disabled={busy != null}
            className="rounded border border-zinc-700 px-2.5 py-1 text-xs text-zinc-400 hover:bg-zinc-800 disabled:opacity-50"
          >
            {busy === "seed" ? "…" : "+ Demo"}
          </button>
          <button
            onClick={onClear}
            disabled={busy != null}
            title="Feed leeren (Demo-Seeds entfernen); Lessons bleiben erhalten"
            className="rounded border border-red-900 px-2.5 py-1 text-xs text-red-400 hover:bg-red-950/40 disabled:opacity-50"
          >
            {busy === "clear" ? "…" : "🗑 Clear"}
          </button>
        </span>
      </div>

      {/* ── market pulse panel ────────────────────────────────────────────── */}
      <MarketPulse market={market} onFocus={focusItem} />

      {/* ── filter row ────────────────────────────────────────────────────── */}
      <div className="flex flex-wrap items-center gap-2 border-b border-zinc-800 px-4 py-2 text-xs">
        <span className="text-zinc-500">KAT:</span>
        <Chip active={cat === null} onClick={() => setCat(null)}>ALLE</Chip>
        {CATEGORIES.map((c) => (
          <Chip key={c} active={cat === c} onClick={() => setCat(cat === c ? null : c)}>{c}</Chip>
        ))}
        <span className="ml-3 text-zinc-500">PRIO:</span>
        <Chip active={prio === null} onClick={() => setPrio(null)}>ALLE</Chip>
        {PRIORITIES.map((p) => (
          <Chip key={p} active={prio === p} onClick={() => setPrio(prio === p ? null : p)}>
            <span className={PRIO_COLOR[p]}>{p}</span>
          </Chip>
        ))}
        <span className="ml-3 text-zinc-500">STATUS:</span>
        {(["open", "correct", "incorrect"] as HypothesisStatus[]).map((s) => (
          <Chip key={s} active={statusFilter === s} onClick={() => setStatusFilter(statusFilter === s ? null : s)}>
            {STATUS_BADGE[s].label}
          </Chip>
        ))}
        <span className="ml-auto text-[10px] text-zinc-600">{items.length} / {allItems.length} angezeigt</span>
        <button
          onClick={() => setShowLessons((v) => !v)}
          className="rounded border border-zinc-700 px-2 py-0.5 text-zinc-400 hover:bg-zinc-800"
        >
          {showLessons ? "Lessons ✕" : "Lessons ☰"}
        </button>
      </div>

      {error && (
        <div className="mx-4 mt-3 rounded border border-red-900 bg-red-950/40 px-3 py-2 text-xs text-red-300">
          API-Fehler: {error}. Backend neu starten:{" "}
          <code className="text-red-200">uvicorn apps.api.main:app --reload</code>
        </div>
      )}

      <div className={`mt-2 grid gap-3 ${showLessons ? "lg:grid-cols-[1fr_320px]" : "grid-cols-1"}`}>
        {/* ── feed ─────────────────────────────────────────────────────────── */}
        <section>
          <div className="grid grid-cols-[78px_1fr_172px_104px] items-center gap-2 border-b border-zinc-800 px-3 py-1 text-[10px] uppercase tracking-wider text-zinc-500">
            <span>Zeit</span>
            <span>Schlagzeile</span>
            <span>Hypothese</span>
            <span className="text-right">Status / Live</span>
          </div>
          {items.length === 0 && (
            <p className="px-3 py-8 text-center text-xs text-zinc-500">
              {allItems.length === 0 ? "Lade echte News…" : "Kein Eintrag für diesen Filter."}
            </p>
          )}
          {items.map((it) => (
            <Row
              key={it.id}
              item={it}
              expanded={expanded === it.id}
              onToggle={() => setExpanded(expanded === it.id ? null : it.id)}
              onFeedback={(ok) => run("fb", () => newsFeedback(it.id, ok))}
              onReeval={() => run("re", () => reevaluateNews(it.id))}
              onDoc={patchItem}
              busy={busy != null}
            />
          ))}
        </section>

        {/* ── lessons knowledge base ───────────────────────────────────────── */}
        {showLessons && (
          <aside className="lg:border-l lg:border-zinc-800 lg:pl-3">
            <h2 className="border-b border-zinc-800 px-1 py-1 text-[10px] uppercase tracking-wider text-sky-400">
              Lessons Learned · {lessons.length}
            </h2>
            {lessons.length === 0 && (
              <p className="px-1 py-4 text-xs text-zinc-600">
                Noch keine Fehlprognosen. Lessons entstehen automatisch bei Soll-vs-Ist-Abweichungen.
              </p>
            )}
            <ul className="space-y-2 py-2">
              {lessons.map((l) => (
                <li key={l.id} className="rounded border border-zinc-800 bg-zinc-900/40 p-2 text-xs">
                  <div className="flex items-center gap-1.5 text-[10px] text-zinc-500">
                    <span className="rounded bg-zinc-800 px-1 text-zinc-400">{l.category}</span>
                    <span className={DIR_COLOR[l.predicted]}>{l.predicted}</span>
                    <span className="text-zinc-600">→</span>
                    <span className={DIR_COLOR[l.actual]}>{l.actual}</span>
                    {l.realized_return != null && (
                      <span className="ml-auto text-zinc-500">{pct(l.realized_return)}</span>
                    )}
                  </div>
                  <p className="mt-1 line-clamp-2 text-zinc-400">“{l.headline}”</p>
                  <p className="mt-1 text-amber-300/80">{l.takeaway}</p>
                </li>
              ))}
            </ul>
          </aside>
        )}
      </div>
    </main>
  );
}

// ── row ───────────────────────────────────────────────────────────────────────
function Row({
  item, expanded, onToggle, onFeedback, onReeval, onDoc, busy,
}: {
  item: NewsItem;
  expanded: boolean;
  onToggle: () => void;
  onFeedback: (correct: boolean) => void;
  onReeval: () => void;
  onDoc: (it: NewsItem) => void;
  busy: boolean;
}) {
  const h = item.hypothesis;
  const st = h ? STATUS_BADGE[h.status] : null;
  const prov = h?.status === "open" && h.provisional_status ? PROV[h.provisional_status] : null;
  return (
    <div id={`news-${item.id}`} className="scroll-mt-24 border-b border-zinc-900 hover:bg-zinc-900/40">
      <div
        onClick={onToggle}
        className="grid cursor-pointer grid-cols-[78px_1fr_172px_104px] items-center gap-2 px-3 py-1.5"
      >
        <span className="text-[11px] text-zinc-500">{fmtTime(item.timestamp)}</span>

        <div className="min-w-0">
          <div className="flex items-center gap-1.5">
            <span className={`h-1.5 w-1.5 shrink-0 rounded-full ${PRIO_DOT[item.priority]}`} />
            <span className="rounded bg-zinc-800 px-1 text-[10px] text-zinc-400">{item.category}</span>
            <span className="truncate text-[10px] text-zinc-600">{item.source}</span>
          </div>
          <p className="truncate text-zinc-200">{item.title}</p>
        </div>

        {h ? (
          <div className="min-w-0">
            <span className={`inline-block rounded border px-1.5 text-[10px] font-semibold ${DIR_BG[h.direction]}`}>
              {h.direction.toUpperCase()}
            </span>
            <span className="ml-1 text-[10px] text-zinc-500">{h.asset} · {(h.confidence * 100).toFixed(0)}%</span>
          </div>
        ) : (
          <span className="text-[10px] text-zinc-600">—</span>
        )}

        <div className="flex flex-col items-end gap-0.5">
          {st && (
            <span className={`inline-block rounded border px-1.5 py-0.5 text-[9px] font-semibold ${st.cls}`}>
              {st.label}
            </span>
          )}
          {prov && (
            <span className={`flex items-center gap-1 text-[10px] ${prov.text}`}>
              <span className={`h-1.5 w-1.5 rounded-full ${prov.dot}`} />
              {pct(h?.provisional_return)} {prov.label}
            </span>
          )}
        </div>
      </div>

      {expanded && (
        <ExpandedRow item={item} h={h} onFeedback={onFeedback} onReeval={onReeval} onDoc={onDoc} busy={busy} />
      )}
    </div>
  );
}

function ExpandedRow({
  item, h, onFeedback, onReeval, onDoc, busy,
}: {
  item: NewsItem;
  h: NewsItem["hypothesis"];
  onFeedback: (correct: boolean) => void;
  onReeval: () => void;
  onDoc: (it: NewsItem) => void;
  busy: boolean;
}) {
  const [lang, setLang] = useState<"de" | "en">("de");
  const [doc, setDoc] = useState<Briefing | null>(item.document);
  const [loadingDoc, setLoadingDoc] = useState(false);

  // lazily generate the bilingual briefing on first open
  useEffect(() => {
    if (doc || loadingDoc) return;
    setLoadingDoc(true);
    getNewsDocument(item.id)
      .then((r) => {
        setDoc(r.document);
        onDoc({ ...item, document: r.document });
      })
      .catch(() => {})
      .finally(() => setLoadingDoc(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="border-t border-zinc-900 bg-zinc-950/60 px-3 py-3 text-xs sm:pl-[90px]">
      {h && (
        <div className="grid gap-x-6 gap-y-1 sm:grid-cols-2">
          <Field label="Richtung"><span className={DIR_COLOR[h.direction]}>{h.direction}</span></Field>
          <Field label="Asset / Scope">{h.asset} <span className="text-zinc-600">({h.scope})</span></Field>
          <Field label="Confidence">{(h.confidence * 100).toFixed(0)}%</Field>
          <Field label="Modell">{h.model}</Field>
          <Field label="Verify-Fenster">{h.verify_after_hours} h</Field>
          <Field label={h.status === "open" ? "Live-Move" : "Realisiert"}>
            <span className={(h.provisional_return ?? h.realized_return ?? 0) < 0 ? "text-red-400" : "text-emerald-400"}>
              {pct(h.status === "open" ? h.provisional_return : h.realized_return)}
            </span>
            {h.status === "open" && h.provisional_status && (
              <span className="ml-1 text-zinc-500">({PROV[h.provisional_status].label})</span>
            )}
          </Field>
        </div>
      )}
      {h && (
        <p className="mt-2 text-zinc-300">
          <span className="text-zinc-500">Hypothese: </span>{h.rationale}
        </p>
      )}

      {/* ── bilingual briefing document ──────────────────────────────────── */}
      <div className="mt-3 rounded border border-zinc-800 bg-zinc-900/40 p-2.5">
        <div className="mb-1.5 flex items-center gap-2">
          <span className="text-[10px] uppercase tracking-wider text-zinc-500">Briefing</span>
          <div className="flex overflow-hidden rounded border border-zinc-700 text-[10px]">
            {(["de", "en"] as const).map((lng) => (
              <button
                key={lng}
                onClick={(e) => { e.stopPropagation(); setLang(lng); }}
                className={`px-2 py-0.5 ${lang === lng ? "bg-amber-900/50 text-amber-200" : "text-zinc-400 hover:bg-zinc-800"}`}
              >
                {lng.toUpperCase()}
              </button>
            ))}
          </div>
          {doc && <span className="text-[10px] text-zinc-600">{doc.model}</span>}
          {item.url && (
            <a
              href={item.url}
              target="_blank"
              rel="noreferrer"
              onClick={(e) => e.stopPropagation()}
              className="ml-auto text-[10px] text-sky-400 hover:underline"
            >
              Quelle ↗
            </a>
          )}
        </div>
        {loadingDoc && <p className="text-zinc-500">Erzeuge Briefing…</p>}
        {doc && (
          <div className="whitespace-pre-wrap leading-relaxed text-zinc-300">
            {renderMd(lang === "de" ? doc.de : doc.en)}
          </div>
        )}
        {!doc && !loadingDoc && <p className="text-zinc-600">Kein Briefing verfügbar.</p>}
      </div>

      {h && (
        <div className="mt-3 flex items-center gap-2" onClick={(e) => e.stopPropagation()}>
          <span className="text-[10px] text-zinc-500">FEEDBACK:</span>
          <button onClick={() => onFeedback(true)} disabled={busy}
            className="rounded border border-emerald-800 px-2 py-0.5 text-[11px] text-emerald-300 hover:bg-emerald-950/50 disabled:opacity-40">
            ✓ Korrekt
          </button>
          <button onClick={() => onFeedback(false)} disabled={busy}
            className="rounded border border-red-800 px-2 py-0.5 text-[11px] text-red-300 hover:bg-red-950/50 disabled:opacity-40">
            ✗ Falsch
          </button>
          <button onClick={onReeval} disabled={busy}
            className="rounded border border-zinc-700 px-2 py-0.5 text-[11px] text-zinc-400 hover:bg-zinc-800 disabled:opacity-40">
            ↻ Neu bewerten
          </button>
        </div>
      )}
    </div>
  );
}

// minimal **bold** markdown -> spans (the briefings use **headings**)
function renderMd(text: string) {
  return text.split(/(\*\*[^*]+\*\*)/g).map((part, i) =>
    part.startsWith("**") && part.endsWith("**") ? (
      <strong key={i} className="text-zinc-100">{part.slice(2, -2)}</strong>
    ) : (
      <span key={i}>{part}</span>
    ),
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex gap-2">
      <span className="w-28 shrink-0 text-zinc-500">{label}</span>
      <span className="text-zinc-300">{children}</span>
    </div>
  );
}

// ── market-pulse panel ────────────────────────────────────────────────────────
function minutesAgo(iso: string): string {
  const m = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 60000));
  if (m < 1) return "gerade eben";
  if (m < 60) return `vor ${m} min`;
  return `vor ${Math.round(m / 60)} h`;
}
const biasColor = (s: number) => (s > 0.15 ? "text-emerald-400" : s < -0.15 ? "text-red-400" : "text-zinc-400");

function BiasBar({ score }: { score: number }) {
  const w = Math.min(Math.abs(score), 1) * 50;
  const pos = score >= 0;
  return (
    <div className="relative h-2 w-full rounded-sm bg-zinc-800">
      <div className="absolute left-1/2 top-0 h-full w-px bg-zinc-600" />
      <div
        className={`absolute top-0 h-full rounded-sm ${pos ? "bg-emerald-500" : "bg-red-500"}`}
        style={pos ? { left: "50%", width: `${w}%` } : { right: "50%", width: `${w}%` }}
      />
    </div>
  );
}

function MarketPulse({ market, onFocus }: { market: MarketSnapshot | null; onFocus: (id: string) => void }) {
  const [open, setOpen] = useState(true);
  if (!market) {
    return (
      <div className="border-b border-zinc-800 px-4 py-3 text-xs text-zinc-500">Marktlage wird geladen…</div>
    );
  }
  const o = market.overall;
  return (
    <div className="border-b border-zinc-800 bg-gradient-to-b from-zinc-900/50 to-transparent px-4 py-3">
      <div className="flex items-center gap-2">
        <button onClick={() => setOpen((v) => !v)} className="text-[10px] text-zinc-500 hover:text-zinc-300">
          {open ? "▾" : "▸"}
        </button>
        <span className="text-[11px] font-bold uppercase tracking-wider text-amber-400">Marktlage</span>
        <span className={`rounded border px-1.5 text-[10px] font-semibold ${DIR_BG[o.score > 0.15 ? "Bullish" : o.score < -0.15 ? "Bearish" : "Neutral"]}`}>
          {o.label_de.toUpperCase()} · {o.score >= 0 ? "+" : ""}{o.score.toFixed(2)}
        </span>
        <span className="text-[10px] text-zinc-600">
          aktualisiert {minutesAgo(market.narrative_at)} · {market.narrative_model}
        </span>
      </div>

      {open && (
        <div className="mt-2 grid gap-x-6 gap-y-3 lg:grid-cols-[1fr_360px]">
          {/* narrative + top hypotheses */}
          <div>
            <p className="max-w-prose text-[13px] leading-relaxed text-zinc-200">{market.narrative}</p>
            {market.top.length > 0 && (
              <div className="mt-3">
                <div className="mb-1 text-[10px] uppercase tracking-wider text-zinc-500">Wichtigste Hypothesen</div>
                <div className="flex flex-wrap gap-1.5">
                  {market.top.map((t) => (
                    <TopChip key={t.id} t={t} onClick={() => onFocus(t.id)} />
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* bias graphics */}
          <div className="space-y-1.5">
            <div className="mb-1 flex items-baseline justify-between">
              <span className="text-[10px] uppercase tracking-wider text-zinc-500">Bias je Kategorie</span>
              <span className="text-[10px] text-zinc-600">
                {o.bullish}▲ {o.bearish}▼ {o.neutral}● · {market.lookback_hours}h
              </span>
            </div>
            {market.categories.length === 0 && <p className="text-[11px] text-zinc-600">Keine Daten.</p>}
            {market.categories.map((c) => (
              <div key={c.category} className="grid grid-cols-[64px_1fr_46px] items-center gap-2">
                <span className="truncate text-[11px] text-zinc-400">{c.category}</span>
                <BiasBar score={c.score} />
                <span className={`text-right font-mono text-[10px] ${biasColor(c.score)}`}>
                  {c.score >= 0 ? "+" : ""}{c.score.toFixed(2)}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function TopChip({ t, onClick }: { t: MarketTop; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      title={t.title}
      className="flex max-w-[230px] items-center gap-1 rounded border border-zinc-800 bg-zinc-900/60 px-1.5 py-0.5 text-[10px] hover:border-zinc-600"
    >
      <span className={`h-1.5 w-1.5 shrink-0 rounded-full ${PRIO_DOT[t.priority]}`} />
      <span className={`font-semibold ${DIR_COLOR[t.direction]}`}>{t.direction.slice(0, 4).toUpperCase()}</span>
      <span className="text-zinc-500">{t.asset}</span>
      <span className="truncate text-zinc-300">{t.title}</span>
    </button>
  );
}

function LlmIndicator({ llm }: { llm: { status: string; s: LlmStatus } | null }) {
  if (!llm) return null;
  const { status, s } = llm;
  let body: React.ReactNode;
  let color = "text-violet-400";
  if (status === "no_model") {
    body = "kein Modell (Heuristik)";
    color = "text-zinc-500";
  } else if (s.running || status === "running" || status === "started") {
    body = <span className="animate-pulse">läuft… (Batch)</span>;
  } else {
    const secs = Math.ceil(s.seconds_until || 0);
    const last =
      s.finished_at != null
        ? ` · zuletzt +${s.hypotheses_upgraded}H/+${s.documents_generated}D`
        : "";
    body = `in ${secs}s${last}`;
  }
  return (
    <span className="flex items-baseline gap-1.5 text-xs" title="LLM-Workflow läuft gebündelt einmal pro Intervall">
      <span className="text-zinc-500">LLM</span>
      <span className={`font-bold ${color}`}>{body}</span>
    </span>
  );
}

function Ticker({ label, value, color = "text-zinc-200" }: { label: string; value: React.ReactNode; color?: string }) {
  return (
    <span className="flex items-baseline gap-1.5 text-xs">
      <span className="text-zinc-500">{label}</span>
      <span className={`font-bold ${color}`}>{value}</span>
    </span>
  );
}

function Chip({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      onClick={onClick}
      className={`rounded px-2 py-0.5 ${active ? "bg-amber-900/50 text-amber-200" : "bg-zinc-800/60 text-zinc-400 hover:bg-zinc-800"}`}
    >
      {children}
    </button>
  );
}
