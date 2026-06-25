"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  getStrategyRegimeMatrix,
  getSwarmConfig,
  getSwarmJob,
  getSwarmLast,
  getSwarmPing,
  runSwarm,
  type DroneStatus,
  type DroneTile,
  type RegimeCode,
  type Stance,
  type StrategyRegimeMatrix,
  type SwarmAllocation,
  type SwarmConfig,
  type SwarmJob,
  type SwarmPing,
  type SwarmRegimeSwitch,
  type SwarmStrategyRef,
  type SwarmVerdict,
} from "@/lib/api";

const cls = (...x: (string | false | undefined)[]) => x.filter(Boolean).join(" ");

const fmt = (v: unknown): string => {
  if (v == null) return "—";
  if (typeof v === "number")
    return Number.isInteger(v) ? String(v) : v.toFixed(v > -1 && v < 1 ? 3 : 2);
  if (typeof v === "boolean") return v ? "ja" : "nein";
  return String(v);
};
const num = (v: number | null | undefined, d = 2) =>
  v == null || !isFinite(v) ? "—" : v.toFixed(d);
const pct = (v: number | null | undefined, d = 1) =>
  v == null || !isFinite(v) ? "—" : `${(v * 100).toFixed(d)}%`;

// drone status → visual language (the four states the spec requires)
const STAT: Record<DroneStatus, { dot: string; text: string; label: string; ring: string; hex: string }> = {
  idle: { dot: "bg-zinc-600", text: "text-zinc-500", label: "Idle", ring: "border-zinc-800", hex: "#3f3f46" },
  computing: { dot: "bg-amber-400", text: "text-amber-300", label: "Computing", ring: "border-amber-500/50", hex: "#fbbf24" },
  done: { dot: "bg-emerald-400", text: "text-emerald-300", label: "Done", ring: "border-emerald-600/40", hex: "#34d399" },
  error: { dot: "bg-red-400", text: "text-red-300", label: "Error", ring: "border-red-600/50", hex: "#f87171" },
};

const STANCE: Record<Stance, { label: string; cls: string }> = {
  risk_on: { label: "Risk-On", cls: "text-emerald-300 border-emerald-600/50 bg-emerald-500/10" },
  risk_off: { label: "Risk-Off", cls: "text-red-300 border-red-600/50 bg-red-500/10" },
  neutral: { label: "Neutral", cls: "text-zinc-300 border-zinc-700 bg-zinc-800/40" },
};

// compact regime tag (matches the radar's weather semantics) for the allowed-regimes chips
const REGIME_TAG: Record<RegimeCode, { short: string; color: string }> = {
  high_vol_trend: { short: "HV-Trend", color: "#f97316" },
  low_vol_trend: { short: "LV-Trend", color: "#22c55e" },
  high_vol_range: { short: "HV-Chop", color: "#eab308" },
  low_vol_range: { short: "LV-Quiet", color: "#60a5fa" },
};

export default function SwarmPage() {
  const [cfg, setCfg] = useState<SwarmConfig | null>(null);
  const [ping, setPing] = useState<SwarmPing | null>(null);
  const [job, setJob] = useState<SwarmJob | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const busy = job != null && ["running", "drones", "commander"].includes(job.status);

  const stopPoll = () => {
    if (pollRef.current) clearInterval(pollRef.current);
    pollRef.current = null;
  };

  const poll = useCallback((id: string) => {
    stopPoll();
    pollRef.current = setInterval(async () => {
      try {
        const j = await getSwarmJob(id);
        setJob(j);
        if (j.status === "done" || j.status === "error") {
          stopPoll();
          getSwarmPing().then(setPing).catch(() => {});
        }
      } catch (e) {
        setError(String(e));
        stopPoll();
      }
    }, 1000);
  }, []);

  useEffect(() => {
    getSwarmConfig().then(setCfg).catch(() => {});
    getSwarmPing().then(setPing).catch(() => {});
    getSwarmLast()
      .then((r) => {
        if (r.job) {
          setJob(r.job);
          if (r.job_id && ["running", "drones", "commander"].includes(r.job.status)) poll(r.job_id);
        }
      })
      .catch(() => {});
    return stopPoll;
  }, [poll]);

  const onRun = async () => {
    setStarting(true);
    setError(null);
    try {
      const r = await runSwarm();
      poll(r.job_id);
      const j = await getSwarmJob(r.job_id);
      setJob(j);
    } catch (e) {
      setError(String(e));
    } finally {
      setStarting(false);
    }
  };

  const drones = job?.drones ?? cfg?.drones.map(droneStub) ?? [];

  return (
    <main className="mx-auto max-w-7xl px-8 py-8">
      <header className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="flex items-center gap-2 text-xl font-semibold tracking-tight">
            <span className="inline-block h-2.5 w-2.5 rounded-sm bg-fuchsia-400" />
            Swarm Command Center
          </h1>
          <p className="mt-1 max-w-2xl text-sm text-zinc-400">
            Hierarchischer Multi-Agent-Desk: lokale <span className="text-sky-300">Worker-Drohnen</span>{" "}
            (Ollama) analysieren Regime, Saisonalität &amp; COT, der{" "}
            <span className="text-fuchsia-300">Commander</span> (Gemini) aggregiert sie zu einem Urteil —
            welche Strategien <span className="text-emerald-300">live</span> gehen und mit welcher Allokation.
          </p>
        </div>
        <div className="flex flex-col items-end gap-2">
          <button
            onClick={onRun}
            disabled={busy || starting}
            className={cls(
              "rounded-md px-4 py-2 text-sm font-semibold transition-colors",
              busy || starting
                ? "cursor-not-allowed bg-zinc-800 text-zinc-500"
                : "bg-fuchsia-600 text-white hover:bg-fuchsia-500",
            )}
          >
            {busy ? "Zyklus läuft …" : starting ? "Starte …" : "▶ Swarm-Zyklus starten"}
          </button>
          <InfraPills ping={ping} />
        </div>
      </header>

      {error && (
        <div className="mb-6 rounded-lg border border-red-700/60 bg-red-950/40 px-4 py-3 text-sm text-red-300">
          {error}
        </div>
      )}

      {job?.regime_switch && <RegimeSwitchBanner sw={job.regime_switch} />}

      <FlowChart drones={drones} status={job?.status} hasVerdict={!!job?.verdict} cfg={cfg} />

      <section className="mb-6">
        <SectionLabel>Swarm Status Monitor</SectionLabel>
        <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
          {drones.map((d) => (
            <DroneCard key={d.drone} d={d} />
          ))}
        </div>
      </section>

      <VerdictWindow job={job} />

      {job?.verdict && (
        <Allocations
          verdict={job.verdict}
          strategies={job.strategies ?? []}
          currentRegime={job.regime_switch?.current_regime ?? null}
        />
      )}
    </main>
  );
}

// ── live-switch banner: the automatic ACTIVE/PAUSED reshuffle on a regime change ──
function RegimeSwitchBanner({ sw }: { sw: SwarmRegimeSwitch }) {
  const color = sw.current_color ?? "#a78bfa";
  const flipped = sw.just_switched && !!sw.previous_regime;
  const act = sw.delta?.activated ?? [];
  const deact = sw.delta?.deactivated ?? [];
  return (
    <section
      className={cls(
        "mb-6 rounded-xl border bg-zinc-900/40 px-5 py-4",
        flipped ? "border-amber-600/50" : "border-zinc-800",
      )}
    >
      <div className="flex flex-wrap items-center gap-x-8 gap-y-3">
        <div className="flex items-center gap-3">
          <span className="relative flex h-2.5 w-2.5">
            {flipped && (
              <span
                className="absolute inline-flex h-full w-full animate-ping rounded-full opacity-70"
                style={{ background: color }}
              />
            )}
            <span className="relative inline-flex h-2.5 w-2.5 rounded-full" style={{ background: color }} />
          </span>
          <div>
            <div className="text-[10px] uppercase tracking-widest text-zinc-500">
              Live-Switch · {sw.benchmark ?? "SPY"}-Regime
            </div>
            <div className="flex items-center gap-2 text-sm">
              {sw.previous_label && (
                <>
                  <span className="text-zinc-500">{sw.previous_label}</span>
                  <span className="text-zinc-600">→</span>
                </>
              )}
              <span className="font-semibold" style={{ color }}>
                {sw.current_label ?? "—"}
              </span>
              {flipped ? (
                <span className="rounded-full border border-amber-600/50 bg-amber-500/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-amber-300">
                  gerade gewechselt
                </span>
              ) : (
                <span className="text-[11px] text-zinc-600">stabil · {sw.bars_in_regime} Bars</span>
              )}
            </div>
          </div>
        </div>

        {sw.summary && (
          <div className="text-xs text-zinc-400">
            <div className="text-[10px] uppercase tracking-widest text-zinc-600">Router-Buch</div>
            <div>
              <span className="text-emerald-300">{sw.summary.active} aktiv</span> /{" "}
              {sw.summary.paused} pausiert von {sw.summary.n_strategies}
            </div>
          </div>
        )}

        {(act.length > 0 || deact.length > 0) && (
          <div className="flex flex-wrap items-center gap-x-6 gap-y-1 text-xs">
            {act.length > 0 && (
              <div>
                <span className="text-[10px] uppercase tracking-widest text-emerald-600">+ Aktiviert</span>{" "}
                <span className="font-mono text-emerald-300">{act.map((a) => a.num).join(", ")}</span>
              </div>
            )}
            {deact.length > 0 && (
              <div>
                <span className="text-[10px] uppercase tracking-widest text-red-600">− Deaktiviert</span>{" "}
                <span className="font-mono text-red-300">{deact.map((a) => a.num).join(", ")}</span>
              </div>
            )}
          </div>
        )}
      </div>
    </section>
  );
}

// ── infrastructure status pills ──────────────────────────────────────────────
function InfraPills({ ping }: { ping: SwarmPing | null }) {
  if (!ping) return <div className="h-5" />;
  const ol = ping.ollama;
  const ge = ping.gemini;
  return (
    <div className="flex items-center gap-2 text-[11px]">
      <Pill
        ok={ol.reachable}
        label={`Ollama · ${ol.model}`}
        okText="online"
        badText="offline → Fallback"
        title={`${ol.base_url}${ol.reachable ? ` · ${ol.models.length} Modelle` : ""}`}
      />
      <Pill
        ok={ge.has_key}
        label={`Gemini · ${ge.model}`}
        okText="Key gesetzt"
        badText="kein Key → Fallback"
        title={`Fallback-Modell: ${ge.fallback_model}`}
      />
    </div>
  );
}

function Pill({ ok, label, okText, badText, title }: { ok: boolean; label: string; okText: string; badText: string; title: string }) {
  return (
    <span
      title={title}
      className={cls(
        "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 font-medium",
        ok ? "border-emerald-700/50 bg-emerald-500/10 text-emerald-300" : "border-amber-700/50 bg-amber-500/10 text-amber-300",
      )}
    >
      <span className={cls("h-1.5 w-1.5 rounded-full", ok ? "bg-emerald-400" : "bg-amber-400")} />
      {label} · {ok ? okText : badText}
    </span>
  );
}

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <div className="mb-3 text-[10px] font-semibold uppercase tracking-widest text-zinc-500">{children}</div>
  );
}

// ── the data-flow schematic (drones → commander → verdict) ───────────────────
function FlowChart({
  drones,
  status,
  hasVerdict,
  cfg,
}: {
  drones: DroneTile[];
  status?: string;
  hasVerdict: boolean;
  cfg: SwarmConfig | null;
}) {
  const W = 1000;
  const H = 280;
  const dY = [22, 108, 194];
  const dH = 64;
  const dW = 236;
  const dX = 16;
  const cmd = { x: 432, y: 92, w: 196, h: 96 };
  const ver = { x: 772, y: 100, w: 212, h: 80 };
  const cmdActive = status === "commander";

  return (
    <section className="mb-6 overflow-hidden rounded-xl border border-zinc-800 bg-zinc-900/40">
      <div className="border-b border-zinc-800 px-5 py-2.5 text-[10px] font-semibold uppercase tracking-widest text-zinc-500">
        System-Weichen · Datenfluss
      </div>
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full" style={{ maxHeight: 300 }}>
        {/* edges: drone → commander */}
        {drones.map((d, i) => {
          const y = dY[i] + dH / 2;
          const x1 = dX + dW;
          const flowing = d.status === "computing";
          const col = d.status === "done" ? d.accent : STAT[d.status].hex;
          return (
            <Edge
              key={`e-${d.drone}`}
              d={`M ${x1} ${y} C ${x1 + 90} ${y}, ${cmd.x - 90} ${cmd.y + cmd.h / 2}, ${cmd.x} ${cmd.y + cmd.h / 2}`}
              color={col}
              flowing={flowing}
              done={d.status === "done"}
            />
          );
        })}
        {/* edge: commander → verdict */}
        <Edge
          d={`M ${cmd.x + cmd.w} ${cmd.y + cmd.h / 2} C ${cmd.x + cmd.w + 70} ${cmd.y + cmd.h / 2}, ${ver.x - 70} ${ver.y + ver.h / 2}, ${ver.x} ${ver.y + ver.h / 2}`}
          color={hasVerdict ? "#34d399" : "#3f3f46"}
          flowing={cmdActive}
          done={hasVerdict}
        />

        {/* drone nodes */}
        {drones.map((d, i) => {
          const st = STAT[d.status];
          return (
            <g key={`n-${d.drone}`}>
              <title>{d.task}</title>
              <rect
                x={dX}
                y={dY[i]}
                width={dW}
                height={dH}
                rx={10}
                fill="#0a0a0b"
                stroke={d.status === "done" ? d.accent : st.hex}
                strokeWidth={d.status === "idle" ? 1 : 1.6}
              />
              <circle cx={dX + 16} cy={dY[i] + 20} r={4} fill={d.status === "done" ? d.accent : st.hex}>
                {d.status === "computing" && (
                  <animate attributeName="opacity" values="1;0.25;1" dur="1s" repeatCount="indefinite" />
                )}
              </circle>
              <text x={dX + 30} y={dY[i] + 24} fill="#e4e4e7" fontSize={13} fontWeight={600}>
                {d.label}
              </text>
              <text x={dX + 16} y={dY[i] + 44} fill="#71717a" fontSize={10.5}>
                {truncate(d.task, 36)}
              </text>
              <text x={dX + dW - 12} y={dY[i] + 24} fill={st.hex} fontSize={10} fontWeight={600} textAnchor="end">
                {st.label.toUpperCase()}
              </text>
            </g>
          );
        })}

        {/* commander node */}
        <g>
          <title>Cloud-Commander (Gemini) — aggregiert die Drohnen-JSONs zu einem Urteil</title>
          <rect
            x={cmd.x}
            y={cmd.y}
            width={cmd.w}
            height={cmd.h}
            rx={12}
            fill="#1a0b1f"
            stroke={hasVerdict ? "#e879f9" : cmdActive ? "#fbbf24" : "#52525b"}
            strokeWidth={1.8}
          />
          <text x={cmd.x + cmd.w / 2} y={cmd.y + 30} fill="#f0abfc" fontSize={13} fontWeight={700} textAnchor="middle">
            COMMANDER
          </text>
          <text x={cmd.x + cmd.w / 2} y={cmd.y + 50} fill="#d4d4d8" fontSize={11} textAnchor="middle">
            {cfg?.gemini.model ?? "Gemini"}
          </text>
          <text x={cmd.x + cmd.w / 2} y={cmd.y + 70} fill="#71717a" fontSize={9.5} textAnchor="middle">
            {cmdActive ? "aggregiert & urteilt …" : `↘ ${cfg?.gemini.fallback_model ?? ""}`}
          </text>
        </g>

        {/* verdict node */}
        <g>
          <rect
            x={ver.x}
            y={ver.y}
            width={ver.w}
            height={ver.h}
            rx={12}
            fill="#052e1a"
            stroke={hasVerdict ? "#34d399" : "#3f3f46"}
            strokeWidth={1.8}
          />
          <text x={ver.x + ver.w / 2} y={ver.y + 32} fill="#6ee7b7" fontSize={13} fontWeight={700} textAnchor="middle">
            DAS URTEIL
          </text>
          <text x={ver.x + ver.w / 2} y={ver.y + 54} fill="#a1a1aa" fontSize={10.5} textAnchor="middle">
            {hasVerdict ? "Routing aktiv" : "wartet auf Zyklus"}
          </text>
        </g>
      </svg>
    </section>
  );
}

function Edge({ d, color, flowing, done }: { d: string; color: string; flowing: boolean; done: boolean }) {
  return (
    <g>
      <path d={d} fill="none" stroke={color} strokeWidth={flowing || done ? 2 : 1} opacity={done || flowing ? 0.9 : 0.35} />
      {flowing && (
        <path d={d} fill="none" stroke={color} strokeWidth={2.4} strokeDasharray="4 10" strokeLinecap="round">
          <animate attributeName="stroke-dashoffset" values="28;0" dur="0.8s" repeatCount="indefinite" />
        </path>
      )}
    </g>
  );
}

// ── drone status tile (the monitor) ──────────────────────────────────────────
function DroneCard({ d }: { d: DroneTile }) {
  const st = STAT[d.status];
  const chips = signalChips(d.signal);
  return (
    <div className={cls("rounded-xl border bg-zinc-900/50 p-4", st.ring)}>
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2">
          <span className="h-2 w-2 rounded-full" style={{ background: d.accent }} />
          <div className="text-sm font-semibold text-zinc-100">{d.label}</div>
        </div>
        <span className={cls("inline-flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wider", st.text)}>
          <span className={cls("h-1.5 w-1.5 rounded-full", st.dot, d.status === "computing" && "animate-ping")} />
          {st.label}
        </span>
      </div>
      <div className="mt-1 text-[11px] text-zinc-500">{d.task}</div>

      <div className="mt-3 min-h-[34px] text-[13px] leading-snug text-zinc-200">
        {d.status === "error" ? (
          <span className="text-red-400">{d.error}</span>
        ) : d.headline ? (
          d.headline
        ) : (
          <span className="text-zinc-600">— bereit —</span>
        )}
      </div>

      {chips.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-1.5">
          {chips.map(([k, v]) => (
            <span key={k} className="rounded bg-zinc-800/70 px-1.5 py-0.5 font-mono text-[10px] text-zinc-400">
              <span className="text-zinc-600">{k}</span> {v}
            </span>
          ))}
        </div>
      )}

      <div className="mt-3 flex items-center justify-between border-t border-zinc-800/80 pt-2 text-[10px] text-zinc-500">
        <span title="Modell, das die Headline erzeugt hat">
          {d.model === "deterministic" ? "Fallback (regelbasiert)" : d.model ?? "—"}
        </span>
        <span className="flex items-center gap-3 font-mono">
          {d.rss_mb != null && <span title="RAM (API-Prozess-RSS)">{d.rss_mb} MB</span>}
          {d.elapsed_ms != null && <span title="Laufzeit">{d.elapsed_ms} ms</span>}
        </span>
      </div>
    </div>
  );
}

// ── the verdict window (prominent center) ────────────────────────────────────
function VerdictWindow({ job }: { job: SwarmJob | null }) {
  const v = job?.verdict;
  const computing = job != null && ["running", "drones", "commander"].includes(job.status);
  const isFallback = v?.source === "deterministic";
  return (
    <section className="mb-6">
      <SectionLabel>Das Urteil · Commander</SectionLabel>
      <div
        className={cls(
          "rounded-xl border bg-gradient-to-br from-zinc-900/80 to-zinc-950 p-6",
          v ? (isFallback ? "border-amber-700/40" : "border-fuchsia-700/40") : "border-zinc-800",
        )}
      >
        {!v && (
          <div className="py-8 text-center text-sm text-zinc-500">
            {computing ? "Commander wartet auf die Drohnen …" : "Noch kein Urteil — starte einen Swarm-Zyklus."}
          </div>
        )}
        {v && (
          <>
            <div className="mb-3 flex flex-wrap items-center gap-3">
              <span className="text-lg font-semibold text-zinc-50">{v.regime_summary}</span>
              <span
                className={cls(
                  "rounded-full border px-2.5 py-1 text-[10px] font-semibold uppercase tracking-wider",
                  isFallback
                    ? "border-amber-600/50 bg-amber-500/10 text-amber-300"
                    : "border-fuchsia-600/50 bg-fuchsia-500/10 text-fuchsia-300",
                )}
                title={v.degraded_reason ?? undefined}
              >
                {isFallback ? "Regelbasierter Fallback" : `Gemini · ${v.model_used}`}
                {v.commander_attempts > 1 ? ` · ${v.commander_attempts} Versuche` : ""}
              </span>
            </div>
            <p className="max-w-3xl text-[15px] leading-relaxed text-zinc-200">{v.verdict}</p>
            {v.risk_note && (
              <div className="mt-4 flex items-start gap-2 rounded-lg border border-zinc-800 bg-zinc-900/60 px-3 py-2 text-sm text-amber-200/90">
                <span className="mt-0.5 text-amber-400">⚠</span>
                <span>{v.risk_note}</span>
              </div>
            )}
          </>
        )}
      </div>
    </section>
  );
}

// ── allocation routing table (regime-conditional, drill-down to the matrix) ──
function Allocations({
  verdict,
  strategies,
  currentRegime,
}: {
  verdict: SwarmVerdict;
  strategies: SwarmStrategyRef[];
  currentRegime: RegimeCode | null;
}) {
  const active = verdict.allocations.filter((a) => a.action === "ACTIVE").length;
  const maxW = Math.max(0.0001, ...verdict.allocations.map((a) => a.weight));
  const byNum = new Map(strategies.map((s) => [s.num, s]));
  return (
    <section>
      <SectionLabel>
        Routing · {active} aktiv / {verdict.allocations.length - active} pausiert · regime-konditional
        <span className="ml-2 normal-case text-zinc-600">(Zeile klicken → Regime-Matrix)</span>
      </SectionLabel>
      <div className="overflow-hidden rounded-xl border border-zinc-800">
        <table className="w-full border-collapse text-sm">
          <thead>
            <tr className="border-b border-zinc-800 bg-zinc-900/70 text-left text-[10px] uppercase tracking-widest text-zinc-500">
              <th className="px-4 py-2.5 font-medium">Strategie</th>
              <th className="px-3 py-2.5 font-medium">Status</th>
              <th className="px-3 py-2.5 font-medium">Gewicht</th>
              <th className="px-3 py-2.5 font-medium">Erlaubte Regimes</th>
              <th className="px-4 py-2.5 font-medium">Begründung</th>
            </tr>
          </thead>
          <tbody>
            {verdict.allocations.map((a) => (
              <AllocRow key={a.num} a={a} maxW={maxW} sref={byNum.get(a.num)} currentRegime={currentRegime} />
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function AllocRow({
  a,
  maxW,
  sref,
  currentRegime,
}: {
  a: SwarmAllocation;
  maxW: number;
  sref?: SwarmStrategyRef;
  currentRegime: RegimeCode | null;
}) {
  const active = a.action === "ACTIVE";
  const allowed = sref?.allowed_regimes ?? [];
  const [open, setOpen] = useState(false);
  const [matrix, setMatrix] = useState<StrategyRegimeMatrix | null>(null);
  const [loading, setLoading] = useState(false);

  const toggle = () => {
    const next = !open;
    setOpen(next);
    if (next && !matrix && !loading) {
      setLoading(true);
      getStrategyRegimeMatrix(a.num)
        .then(setMatrix)
        .catch(() => {})
        .finally(() => setLoading(false));
    }
  };

  return (
    <>
      <tr
        onClick={toggle}
        className={cls(
          "cursor-pointer border-b border-zinc-900 hover:bg-zinc-900/40",
          active && "bg-emerald-950/10",
        )}
      >
        <td className="px-4 py-2.5">
          <div className="flex items-center gap-2">
            <svg
              className={cls("h-3 w-3 text-zinc-600 transition-transform", open && "rotate-90")}
              viewBox="0 0 12 12"
              fill="none"
            >
              <path d="M4.5 3L7.5 6L4.5 9" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
            </svg>
            <div>
              <div className="text-zinc-100">{a.name ?? a.num}</div>
              <div className="font-mono text-[10px] text-zinc-600">#{a.num}</div>
            </div>
          </div>
        </td>
        <td className="px-3 py-2.5">
          {active ? (
            <span className="inline-flex items-center gap-1.5 rounded-full border border-emerald-600/60 bg-emerald-500/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-emerald-300">
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" /> Active
            </span>
          ) : (
            <span className="inline-flex items-center gap-1.5 rounded-full border border-zinc-700 bg-zinc-800/40 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-zinc-500">
              <span className="h-1.5 w-1.5 rounded-full bg-zinc-600" /> Paused
            </span>
          )}
        </td>
        <td className="px-3 py-2.5">
          <div className="flex items-center gap-2">
            <div className="h-1.5 w-20 overflow-hidden rounded-full bg-zinc-800">
              <div
                className={cls("h-full rounded-full", active ? "bg-emerald-500" : "bg-zinc-700")}
                style={{ width: `${active ? (a.weight / maxW) * 100 : 0}%` }}
              />
            </div>
            <span className="font-mono text-xs tabular-nums text-zinc-300">
              {active ? `${(a.weight * 100).toFixed(1)}%` : "—"}
            </span>
          </div>
        </td>
        <td className="px-3 py-2.5">
          {allowed.length > 0 ? (
            <div className="flex flex-wrap gap-1">
              {allowed.map((r) => (
                <RegimeChip key={r} code={r} live={r === currentRegime} />
              ))}
            </div>
          ) : sref ? (
            <span className="text-[10px] text-zinc-600">keines im Buch</span>
          ) : (
            <span className="text-[10px] text-zinc-700">—</span>
          )}
        </td>
        <td className="px-4 py-2.5 text-xs text-zinc-400">{a.reason}</td>
      </tr>
      {open && (
        <tr className="border-b border-zinc-900 bg-zinc-950/60">
          <td colSpan={5} className="px-0 py-0">
            <RegimeMatrixDetail matrix={matrix} loading={loading} currentRegime={currentRegime} />
          </td>
        </tr>
      )}
    </>
  );
}

function RegimeChip({ code, live }: { code: RegimeCode; live: boolean }) {
  const t = REGIME_TAG[code];
  return (
    <span
      className={cls(
        "inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[9px] font-medium",
        live ? "ring-1 ring-zinc-100/40" : "",
      )}
      style={{ background: `${t.color}22`, color: t.color }}
      title={live ? "aktuelles Regime" : undefined}
    >
      <span className="h-1.5 w-1.5 rounded-sm" style={{ background: t.color }} />
      {t.short}
    </span>
  );
}

// the per-strategy Regime Performance Matrix (2.2) — daily cells + tagged-trade stats
function RegimeMatrixDetail({
  matrix,
  loading,
  currentRegime,
}: {
  matrix: StrategyRegimeMatrix | null;
  loading: boolean;
  currentRegime: RegimeCode | null;
}) {
  if (loading)
    return <div className="px-5 py-3 text-xs text-zinc-500">Lade Regime-Performance-Matrix …</div>;
  if (!matrix || !matrix.ok)
    return <div className="px-5 py-3 text-xs text-zinc-600">Keine Regime-Matrix verfügbar (kein Trade-Log/Buch-Eintrag).</div>;
  const cells = matrix.matrix?.cells;
  const ts = matrix.trade_stats;
  return (
    <div className="px-5 py-3">
      <div className="mb-2 text-[10px] uppercase tracking-widest text-zinc-600">
        Regime-Performance-Matrix · {matrix.n_trades} getaggte Trades · Benchmark {matrix.benchmark}
        {matrix.best_regime && (
          <span className="ml-2 normal-case text-zinc-500">
            bestes Regime: {REGIME_TAG[matrix.best_regime]?.short ?? matrix.best_regime}
          </span>
        )}
      </div>
      <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
        {matrix.regimes.map((r) => {
          const c = cells?.[r.code];
          const t = ts?.[r.code];
          const isAllowed = matrix.allowed_market_regimes.includes(r.code);
          const isCur = r.code === currentRegime;
          return (
            <div
              key={r.code}
              className={cls(
                "rounded-lg border p-2",
                isCur ? "border-zinc-100/30" : "border-zinc-800",
                isAllowed ? "bg-emerald-950/20" : "bg-zinc-900/40",
              )}
            >
              <div className="flex items-center justify-between gap-1">
                <span className="flex items-center gap-1 text-[11px] text-zinc-300">
                  <span className="h-2 w-2 rounded-sm" style={{ background: REGIME_TAG[r.code]?.color }} />
                  {REGIME_TAG[r.code]?.short ?? r.label}
                </span>
                {isAllowed && <span className="text-[8px] uppercase text-emerald-400">erlaubt</span>}
                {isCur && !isAllowed && <span className="text-[8px] uppercase text-zinc-400">live</span>}
              </div>
              <div className="mt-1.5 space-y-0.5 font-mono text-[10px] text-zinc-400">
                <div>
                  S {num(c?.sharpe, 1)} · PF {num(c?.profit_factor, 1)}
                </div>
                <div>
                  WR {pct(c?.win_rate, 0)} · {c?.n ?? 0} Bars
                </div>
                {t && t.n_trades > 0 && (
                  <div className="text-zinc-600">
                    {t.n_trades} Trades · Win {pct(t.win_rate, 0)}
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ── helpers ──────────────────────────────────────────────────────────────────
function droneStub(d: { key: string; label: string; task: string; accent: string }): DroneTile {
  return {
    drone: d.key, label: d.label, task: d.task, accent: d.accent, status: "idle",
    ok: null, signal: null, headline: null, model: null, stance: null,
    elapsed_ms: null, rss_mb: null, error: null,
  };
}

function truncate(s: string, n: number): string {
  return s.length > n ? s.slice(0, n - 1) + "…" : s;
}

/** Pick the primitive (non-array/object) signal fields for the compact chip row. */
function signalChips(signal: Record<string, unknown> | null): [string, string][] {
  if (!signal) return [];
  const out: [string, string][] = [];
  for (const [k, v] of Object.entries(signal)) {
    if (k === "stance") continue;
    if (v == null || typeof v === "object") continue;
    out.push([k, fmt(v)]);
    if (out.length >= 6) break;
  }
  return out;
}
