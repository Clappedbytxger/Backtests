"use client";

import Link from "next/link";
import { use, useEffect, useState } from "react";
import {
  completeLesson,
  generateContent,
  getAcademyModule,
  submitQuiz,
  type AcademyModuleDetail,
  type GeneratedContent,
} from "@/lib/api";
import Lesson from "../components/Lesson";

const slug = (s: string) => s.toLowerCase().replace(/[^a-z0-9]+/g, "-").slice(0, 40);

export default function AcademyModuleClient({ params }: { params: Promise<{ moduleId: string }> }) {
  const { moduleId } = use(params);
  const [detail, setDetail] = useState<AcademyModuleDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<Set<string>>(new Set());

  const load = () =>
    getAcademyModule(moduleId, true)
      .then((d) => {
        setDetail(d);
        setDone(new Set((d.module.completed_lessons ?? [])));
      })
      .catch((e) => setError(String(e)));

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [moduleId]);

  if (error)
    return (
      <main className="mx-auto max-w-5xl p-8">
        <div className="rounded-lg border border-red-900 bg-red-950/40 p-4 text-sm text-red-300">{error}</div>
      </main>
    );
  if (!detail) return <main className="mx-auto max-w-5xl p-8 text-zinc-400">Lädt…</main>;

  const m = detail.module;

  const toggle = async (topic: string) => {
    const id = slug(topic);
    if (done.has(id)) return; // completion is monotonic
    setDone((prev) => new Set(prev).add(id));
    await completeLesson(m.id, id);
    load();
  };

  return (
    <main className="mx-auto max-w-5xl p-8">
      <Link href="/academy" className="text-sm text-zinc-500 hover:text-zinc-300">
        ← Zur Roadmap
      </Link>

      <div className="mt-3 flex flex-wrap items-end justify-between gap-3">
        <div>
          <div className="font-mono text-xs uppercase tracking-wide text-zinc-500">
            Modul {m.index} · {m.sessions} Sitzungen
          </div>
          <h1 className="mt-1 text-3xl font-semibold tracking-tight">{m.title}</h1>
          <p className="mt-1 text-sm text-zinc-400">{m.subtitle}</p>
        </div>
        <StatusBadge status={m.status} xp={m.xp} />
      </div>

      <div className="mt-8 grid gap-8 lg:grid-cols-[1fr_280px]">
        {/* lesson body */}
        <article>
          {m.content_md ? (
            <Lesson markdown={m.content_md} />
          ) : (
            <div className="rounded-lg border border-dashed border-zinc-700 p-6 text-sm text-zinc-500">
              Der ausformulierte Lehrtext für dieses Modul folgt. Die Visualisierungen unten
              sind bereits interaktiv.
            </div>
          )}
          <Practice moduleId={m.id} initial={detail.generated} onScored={load} />
        </article>

        {/* sidebar */}
        <aside className="space-y-4 lg:sticky lg:top-6 lg:self-start">
          <SideCard title="Repo-Anker" body={m.repo_anchor} accent="text-blue-300" />
          <SideCard title="Payoff" body={m.payoff} accent="text-emerald-300" />
          <div className="rounded-lg border border-zinc-800 bg-zinc-900/40 p-3">
            <div className="mb-2 text-xs font-medium uppercase tracking-wide text-zinc-500">
              Lektionen
            </div>
            <ul className="space-y-2">
              {m.topics.map((t) => {
                const checked = done.has(slug(t));
                return (
                  <li key={t}>
                    <button
                      onClick={() => toggle(t)}
                      className="flex w-full items-start gap-2 text-left text-sm hover:text-zinc-100"
                    >
                      <span
                        className={`mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded border text-[10px] ${
                          checked
                            ? "border-emerald-500 bg-emerald-500/20 text-emerald-400"
                            : "border-zinc-600 text-transparent"
                        }`}
                      >
                        ✓
                      </span>
                      <span className={checked ? "text-zinc-400 line-through" : "text-zinc-300"}>{t}</span>
                    </button>
                  </li>
                );
              })}
            </ul>
          </div>
          <SideCard title="Vertiefung" body={m.depth} accent="text-zinc-400" />
        </aside>
      </div>
    </main>
  );
}

function StatusBadge({ status, xp }: { status: string; xp: number }) {
  const map: Record<string, string> = {
    completed: "border-emerald-500 text-emerald-300",
    in_progress: "border-amber-500 text-amber-300",
    available: "border-blue-500 text-blue-300",
    locked: "border-zinc-700 text-zinc-500",
  };
  const label: Record<string, string> = {
    completed: "Abgeschlossen",
    in_progress: "In Arbeit",
    available: "Verfügbar",
    locked: "Gesperrt",
  };
  return (
    <div className="flex items-center gap-2">
      <span className={`rounded-full border px-3 py-1 text-xs ${map[status]}`}>{label[status]}</span>
      <span className="rounded-full border border-zinc-700 px-3 py-1 text-xs text-zinc-400">{xp} XP</span>
    </div>
  );
}

function SideCard({ title, body, accent }: { title: string; body: string; accent: string }) {
  return (
    <div className="rounded-lg border border-zinc-800 bg-zinc-900/40 p-3">
      <div className="mb-1 text-xs font-medium uppercase tracking-wide text-zinc-500">{title}</div>
      <p className={`text-sm leading-snug ${accent}`}>{body}</p>
    </div>
  );
}

/** Agent-generated exercises + quiz. Loads lazily; refresh is interval-gated server-side. */
function Practice({
  moduleId,
  initial,
  onScored,
}: {
  moduleId: string;
  initial?: GeneratedContent | null;
  onScored: () => void;
}) {
  const [gen, setGen] = useState<GeneratedContent | null>(initial ?? null);
  const [loading, setLoading] = useState(false);
  const [answers, setAnswers] = useState<Record<number, number>>({});
  const [result, setResult] = useState<string | null>(null);

  const run = async (force: boolean) => {
    setLoading(true);
    setResult(null);
    try {
      const g = await generateContent(moduleId, force);
      if (g.ok) setGen(g);
    } finally {
      setLoading(false);
    }
  };

  const grade = async () => {
    if (!gen?.quiz?.length) return;
    const correct = gen.quiz.filter((q, i) => answers[i] === q.answer_index).length;
    const score = correct / gen.quiz.length;
    setResult(`${correct}/${gen.quiz.length} richtig (${Math.round(score * 100)}%)`);
    await submitQuiz(moduleId, score, gen.quiz.length);
    onScored();
  };

  return (
    <section className="mt-10 border-t border-zinc-800 pt-6">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">Übungen &amp; Quiz</h2>
        <button
          onClick={() => run(true)}
          disabled={loading}
          className="rounded-md border border-zinc-700 bg-zinc-800 px-3 py-1.5 text-xs text-zinc-200 hover:border-zinc-500 disabled:opacity-50"
        >
          {loading ? "Generiere…" : gen ? "↻ Neue Aufgaben" : "Aufgaben generieren"}
        </button>
      </div>

      {!gen && (
        <p className="mt-3 text-sm text-zinc-500">
          Der Tutor-Agent erzeugt nach Bedarf neue Übungen, ein aktuelles Marktbeispiel und ein
          Quiz (intervall-gegatet — nicht bei jedem Klick neu).
        </p>
      )}

      {gen && (
        <div className="mt-4 space-y-5">
          {gen.market_example && (
            <div className="rounded-lg border border-blue-900/60 bg-blue-950/20 p-3 text-sm text-zinc-300">
              <span className="font-medium text-blue-300">Marktbeispiel: </span>
              {gen.market_example}
            </div>
          )}

          {!!gen.exercises?.length && (
            <ol className="ml-5 list-decimal space-y-2 text-sm text-zinc-300">
              {gen.exercises.map((ex, i) => (
                <li key={i}>{ex.prompt}</li>
              ))}
            </ol>
          )}

          {!!gen.quiz?.length && (
            <div className="space-y-4">
              {gen.quiz.map((q, qi) => (
                <div key={qi} className="rounded-lg border border-zinc-800 bg-zinc-900/40 p-3">
                  <div className="mb-2 text-sm font-medium text-zinc-200">
                    {qi + 1}. {q.question}
                  </div>
                  <div className="grid gap-1.5">
                    {q.options.map((opt, oi) => {
                      const picked = answers[qi] === oi;
                      const reveal = result != null;
                      const correct = oi === q.answer_index;
                      return (
                        <button
                          key={oi}
                          onClick={() => !reveal && setAnswers((a) => ({ ...a, [qi]: oi }))}
                          className={`rounded border px-3 py-1.5 text-left text-sm transition ${
                            reveal && correct
                              ? "border-emerald-500 bg-emerald-500/10 text-emerald-200"
                              : reveal && picked
                                ? "border-red-500 bg-red-500/10 text-red-200"
                                : picked
                                  ? "border-blue-500 bg-blue-500/10 text-zinc-100"
                                  : "border-zinc-700 text-zinc-300 hover:border-zinc-500"
                          }`}
                        >
                          {opt}
                        </button>
                      );
                    })}
                  </div>
                </div>
              ))}
              <div className="flex items-center gap-3">
                <button
                  onClick={grade}
                  className="rounded-md border border-emerald-700 bg-emerald-900/40 px-4 py-1.5 text-sm text-emerald-200 hover:border-emerald-500"
                >
                  Auswerten
                </button>
                {result && <span className="text-sm text-zinc-300">{result}</span>}
              </div>
            </div>
          )}

          {!!gen.books?.length && (
            <div className="text-xs text-zinc-500">
              Vertiefung aus deiner Bibliothek:{" "}
              {gen.books.map((b, i) => (
                <span key={b.rel}>
                  {i > 0 && " · "}
                  <span className="text-zinc-400">{b.title}</span>
                </span>
              ))}
            </div>
          )}
        </div>
      )}
    </section>
  );
}
