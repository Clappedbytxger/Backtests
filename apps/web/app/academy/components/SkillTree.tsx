"use client";

import Link from "next/link";
import type { AcademyModule, ModuleStatus } from "@/lib/api";

const STATUS: Record<ModuleStatus, { ring: string; bg: string; dot: string; label: string }> = {
  completed: { ring: "border-emerald-500", bg: "bg-emerald-500/10", dot: "#22c55e", label: "abgeschlossen" },
  in_progress: { ring: "border-amber-500", bg: "bg-amber-500/10", dot: "#eab308", label: "läuft" },
  available: { ring: "border-blue-500", bg: "bg-blue-500/10", dot: "#3b82f6", label: "verfügbar" },
  locked: { ring: "border-zinc-800", bg: "bg-zinc-900/40", dot: "#3f3f46", label: "gesperrt" },
};

const LEVEL_LABEL: Record<string, string> = {
  foundation: "Grundlagen",
  core: "Kern",
  advanced: "Fortgeschritten",
  senior: "Senior Quant",
};

// Thematic tracks — a subtle left-edge accent per card + a legend. Status colour
// (border/fill) stays dominant; the track colour only tints the left edge.
const TRACK: Record<string, { label: string; color: string }> = {
  core: { label: "Kern-Mathematik", color: "#3b82f6" },
  validation: { label: "Validierung & Robustheit", color: "#f59e0b" },
  statarb: { label: "Statistical Arbitrage", color: "#10b981" },
  microstructure: { label: "Mikrostruktur & Execution", color: "#06b6d4" },
  risk: { label: "Risiko & Prop", color: "#ef4444" },
  alpha: { label: "Alpha-Quellen", color: "#a855f7" },
  derivatives: { label: "Derivate & Vol", color: "#ec4899" },
  ml: { label: "Machine Learning", color: "#84cc16" },
};

// Layout geometry (px). Positions come from each module's data-driven {col,row}.
const COL_W = 280;
const ROW_H = 128;
const PAD = 36;
const CARD_W = 232;
const CARD_H = 96;

const cardX = (col: number) => PAD + col * COL_W;
const cardY = (row: number) => PAD + row * ROW_H;

export default function SkillTree({ modules }: { modules: AcademyModule[] }) {
  const byId = new Map(modules.map((m) => [m.id, m]));
  const maxCol = Math.max(...modules.map((m) => m.pos.col));
  const maxRow = Math.max(...modules.map((m) => m.pos.row));
  const width = PAD * 2 + maxCol * COL_W + CARD_W;
  const height = PAD * 2 + maxRow * ROW_H + CARD_H;

  // Prerequisite edges: prereq bottom-center -> module top-center.
  const edges = modules.flatMap((m) =>
    m.prerequisites
      .map((pid) => byId.get(pid))
      .filter((p): p is AcademyModule => !!p)
      .map((p) => ({
        key: `${p.id}->${m.id}`,
        x1: cardX(p.pos.col) + CARD_W / 2,
        y1: cardY(p.pos.row) + CARD_H,
        x2: cardX(m.pos.col) + CARD_W / 2,
        y2: cardY(m.pos.row),
        done: p.status === "completed",
      })),
  );

  return (
    <div>
      <div className="overflow-x-auto pb-4">
      <div className="relative" style={{ width, height }}>
        <svg
          className="absolute inset-0 pointer-events-none"
          width={width}
          height={height}
          aria-hidden
        >
          {edges.map((e) => {
            const midY = (e.y1 + e.y2) / 2;
            return (
              <path
                key={e.key}
                d={`M ${e.x1} ${e.y1} C ${e.x1} ${midY}, ${e.x2} ${midY}, ${e.x2} ${e.y2}`}
                fill="none"
                stroke={e.done ? "#22c55e" : "#3f3f46"}
                strokeWidth={2}
                strokeDasharray={e.done ? undefined : "5 4"}
              />
            );
          })}
        </svg>

        {modules.map((m) => {
          const s = STATUS[m.status];
          const locked = m.status === "locked";
          const trackColor = m.track ? TRACK[m.track]?.color : undefined;
          const inner = (
            <div
              className={`flex h-full flex-col justify-between rounded-xl border ${s.ring} ${s.bg} p-3 transition ${
                locked ? "opacity-55" : "hover:border-zinc-400 hover:shadow-lg hover:shadow-black/40"
              }`}
              style={trackColor ? { borderLeftWidth: 3, borderLeftColor: trackColor } : undefined}
            >
              <div className="flex items-start justify-between gap-2">
                <div>
                  <div className="font-mono text-[10px] uppercase tracking-wide text-zinc-500">
                    Modul {m.index} · {LEVEL_LABEL[m.level] ?? m.level}
                  </div>
                  <div className="mt-0.5 text-sm font-semibold leading-tight text-zinc-100">
                    {m.title}
                  </div>
                </div>
                <span
                  className="mt-1 h-2.5 w-2.5 shrink-0 rounded-full"
                  style={{ background: s.dot }}
                  title={s.label}
                />
              </div>
              <div>
                <div className="mb-1 flex items-center justify-between text-[10px] text-zinc-500">
                  <span>{m.sessions} Sitzungen</span>
                  <span>{m.progress_pct}%</span>
                </div>
                <div className="h-1 overflow-hidden rounded-full bg-zinc-800">
                  <div
                    className="h-full rounded-full"
                    style={{ width: `${m.progress_pct}%`, background: s.dot }}
                  />
                </div>
              </div>
            </div>
          );
          const style = {
            left: cardX(m.pos.col),
            top: cardY(m.pos.row),
            width: CARD_W,
            height: CARD_H,
          } as const;
          return locked ? (
            <div key={m.id} className="absolute cursor-not-allowed" style={style}>
              {inner}
            </div>
          ) : (
            <Link key={m.id} href={`/academy/${m.id}`} className="absolute" style={style}>
              {inner}
            </Link>
          );
        })}
      </div>
      </div>

      {/* Track legend — only the tracks actually present in the curriculum. */}
      <div className="mt-4 flex flex-wrap gap-x-4 gap-y-1.5 border-t border-zinc-800 pt-3">
        {Object.entries(TRACK)
          .filter(([key]) => modules.some((m) => m.track === key))
          .map(([key, t]) => (
            <span key={key} className="flex items-center gap-1.5 text-xs text-zinc-400">
              <span className="h-2.5 w-2.5 rounded-sm" style={{ background: t.color }} />
              {t.label}
            </span>
          ))}
      </div>
    </div>
  );
}
