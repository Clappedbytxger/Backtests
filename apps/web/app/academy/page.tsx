"use client";

import { useEffect, useState } from "react";
import {
  getBooks,
  getCurriculum,
  type AcademyCurriculum,
  type AcademyModule,
  type Book,
  type ModuleLevel,
} from "@/lib/api";
import { useMode } from "@/lib/mode";
import { IconBeaker, IconCheckCircle, IconCode, IconEye, IconLock } from "@/lib/icons";
import SkillTree from "./components/SkillTree";

// Three named stages layered over the curriculum's finer levels. Stage 3 (Quant Dev)
// is the math-heavy track and is only visible in Developer mode.
interface Stage {
  key: string;
  name: string;
  Icon: (p: { className?: string }) => React.ReactNode;
  desc: string;
  levels: ModuleLevel[];
  devOnly: boolean;
  accent: string;
}

const STAGES: Stage[] = [
  {
    key: "observer",
    name: "Observer",
    Icon: IconEye,
    desc: "Grundlagen der Marktanalyse und Orientierung in der Oberfläche.",
    levels: ["foundation"],
    devOnly: false,
    accent: "#3b82f6",
  },
  {
    key: "researcher",
    name: "Researcher",
    Icon: IconBeaker,
    desc: "Alpha-Fabrik, Saisonalität und erste eigene Auswertungen.",
    levels: ["core"],
    devOnly: false,
    accent: "#10b981",
  },
  {
    key: "quantdev",
    name: "Quant Dev",
    Icon: IconCode,
    desc: "Code-Anpassung, Monte-Carlo-Simulation und statistische Signifikanz.",
    levels: ["advanced", "senior"],
    devOnly: true,
    accent: "#a855f7",
  },
];

const stageOf = (level: ModuleLevel) =>
  STAGES.find((s) => s.levels.includes(level)) ?? STAGES[STAGES.length - 1];

export default function AcademyPage() {
  const { isDev } = useMode();
  const [cur, setCur] = useState<AcademyCurriculum | null>(null);
  const [books, setBooks] = useState<Book[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getCurriculum().then(setCur).catch((e) => setError(String(e)));
    getBooks().then((b) => setBooks(b.books)).catch(() => {});
  }, []);

  if (error) {
    return (
      <main className="mx-auto max-w-6xl p-8">
        <div className="rounded-lg border border-red-900 bg-red-950/40 p-4 text-sm text-red-300">
          API nicht erreichbar ({error}). Starte sie mit{" "}
          <code className="text-red-200">uvicorn apps.api.main:app</code>.
        </div>
      </main>
    );
  }
  if (!cur) return <main className="mx-auto max-w-6xl p-8 text-zinc-400">Lädt…</main>;

  const total = cur.modules.length;
  const done = cur.totals.modules_completed;
  const booksByCat = books.reduce<Record<string, Book[]>>((acc, b) => {
    (acc[b.category] ??= []).push(b);
    return acc;
  }, {});

  // Stage 3 (Quant Dev) modules are hidden in Simple mode → beginners see a clean,
  // non-intimidating path; the math track unlocks with Developer mode.
  const visibleModules = isDev
    ? cur.modules
    : cur.modules.filter((m) => !stageOf(m.level).devOnly);
  const hiddenCount = cur.modules.length - visibleModules.length;

  return (
    <main className="mx-auto max-w-6xl p-8">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-3xl font-semibold tracking-tight">Quant Academy</h1>
          <p className="mt-1 text-sm text-zinc-400">{cur.subtitle}</p>
        </div>
        <div className="flex gap-3">
          <Stat label="Module" value={`${done}/${total}`} />
          <Stat label="XP" value={cur.totals.xp} />
          <Stat label="Streak" value={`${cur.totals.streak_days} T`} />
        </div>
      </div>

      <p className="mt-4 max-w-3xl rounded-lg border border-zinc-800 bg-zinc-900/40 p-3 text-sm text-zinc-400">
        {cur.design_principle}
      </p>

      <div className="mt-3 h-2 overflow-hidden rounded-full bg-zinc-800">
        <div
          className="h-full rounded-full bg-emerald-500 transition-all"
          style={{ width: `${total ? (100 * done) / total : 0}%` }}
        />
      </div>

      <h2 className="mt-10 text-lg font-semibold">Deine Stufen</h2>
      <p className="mb-4 text-xs text-zinc-500">
        Drei Stufen vom Einsteiger zum Quant. Schließe alle Module einer Stufe ab, um ihr
        Badge freizuschalten.
      </p>
      <StageOverview modules={cur.modules} isDev={isDev} />

      <h2 className="mt-10 text-lg font-semibold">Lernpfad</h2>
      <p className="mb-4 text-xs text-zinc-500">
        Klicke ein <span className="text-blue-400">verfügbares</span> Modul an. Gesperrte
        Module brauchen erst ihre Voraussetzungen.
      </p>
      <div className="rounded-xl border border-zinc-800 bg-zinc-950 p-4">
        <SkillTree modules={visibleModules} />
      </div>
      {hiddenCount > 0 && (
        <div className="mt-3 flex items-center gap-2.5 rounded-lg border border-purple-900/60 bg-purple-950/20 p-3 text-sm text-purple-200">
          <IconLock className="h-4 w-4 shrink-0 text-purple-300" />
          <span>
            <strong>Stufe 3 · Quant Dev</strong> ist ausgeblendet ({hiddenCount} Module mit
            Mathematik und Code). Oben rechts auf <strong>„Dev"</strong> umschalten, um sie
            freizuschalten.
          </span>
        </div>
      )}

      <h2 className="mt-12 text-lg font-semibold">
        Lokale Bibliothek <span className="text-sm font-normal text-zinc-500">({books.length} Bücher)</span>
      </h2>
      <p className="mb-3 text-xs text-zinc-500">
        Module ziehen vertiefende Passagen aus diesen lokalen Büchern (konfigurierbar via{" "}
        <code className="text-zinc-400">books_dir</code>).
      </p>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {Object.entries(booksByCat).map(([cat, list]) => (
          <div key={cat} className="rounded-lg border border-zinc-800 bg-zinc-900/40 p-3">
            <div className="mb-2 text-xs font-medium uppercase tracking-wide text-zinc-500">
              {cat}
            </div>
            <ul className="space-y-1.5">
              {list.map((b) => (
                <li key={b.rel} className="text-sm leading-snug">
                  <span className="text-zinc-200">{b.title}</span>
                  {b.author && <span className="text-zinc-500"> — {b.author}</span>}
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </main>
  );
}

function Stat({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-lg border border-zinc-800 bg-zinc-900/60 px-4 py-2 text-center">
      <div className="text-xl font-semibold text-zinc-100">{value}</div>
      <div className="text-[11px] uppercase tracking-wide text-zinc-500">{label}</div>
    </div>
  );
}

/** Three stage cards (Observer → Researcher → Quant Dev) with per-stage progress and an
 *  unlockable badge. Counts come from the full module list, so they stay honest even when
 *  the Quant-Dev stage is hidden in Simple mode. */
function StageOverview({ modules, isDev }: { modules: AcademyModule[]; isDev: boolean }) {
  return (
    <div className="grid gap-3 sm:grid-cols-3">
      {STAGES.map((stage, i) => {
        const inStage = modules.filter((m) => stage.levels.includes(m.level));
        const completed = inStage.filter((m) => m.status === "completed").length;
        const totalN = inStage.length;
        const pct = totalN ? Math.round((100 * completed) / totalN) : 0;
        const earned = totalN > 0 && completed === totalN;
        const locked = stage.devOnly && !isDev;
        return (
          <div
            key={stage.key}
            className="relative overflow-hidden rounded-xl border bg-zinc-900/40 p-4"
            style={{
              borderColor: earned ? stage.accent : "#27272a",
              boxShadow: earned ? `0 0 24px ${stage.accent}33` : undefined,
            }}
          >
            <div className="flex items-start justify-between">
              <div className="flex items-start gap-3">
                <div
                  className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border"
                  style={{
                    borderColor: stage.accent + "40",
                    background: stage.accent + "14",
                    color: stage.accent,
                  }}
                >
                  <stage.Icon className="h-5 w-5" />
                </div>
                <div>
                  <div className="text-[10px] font-semibold uppercase tracking-[0.18em] text-zinc-500">
                    Stufe {i + 1}
                  </div>
                  <div className="mt-0.5 text-base font-semibold text-zinc-100">{stage.name}</div>
                </div>
              </div>
              {/* badge: filled check when the whole stage is done; lock when dev-gated */}
              <div
                className="flex h-8 w-8 items-center justify-center rounded-full border"
                style={{
                  borderColor: earned ? stage.accent : "#3f3f46",
                  background: earned ? stage.accent + "22" : "transparent",
                  color: earned ? stage.accent : "#52525b",
                }}
                title={
                  earned ? "Badge freigeschaltet" : locked ? "Im Developer Mode verfügbar" : "Schließe alle Module ab"
                }
              >
                {earned ? (
                  <IconCheckCircle className="h-4 w-4" />
                ) : locked ? (
                  <IconLock className="h-4 w-4" />
                ) : (
                  <span className="h-2 w-2 rounded-full bg-current" />
                )}
              </div>
            </div>

            <p className="mt-2 text-xs leading-snug text-zinc-400">{stage.desc}</p>

            <div className="mt-3 flex items-center justify-between text-[11px] text-zinc-500">
              <span>
                {completed}/{totalN} Module
              </span>
              <span>{locked ? "im Dev Mode" : `${pct}%`}</span>
            </div>
            <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-zinc-800">
              <div
                className="h-full rounded-full transition-all"
                style={{ width: `${pct}%`, background: stage.accent }}
              />
            </div>
          </div>
        );
      })}
    </div>
  );
}
