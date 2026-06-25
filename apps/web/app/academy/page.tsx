"use client";

import { useEffect, useState } from "react";
import {
  getBooks,
  getCurriculum,
  type AcademyCurriculum,
  type Book,
} from "@/lib/api";
import SkillTree from "./components/SkillTree";

export default function AcademyPage() {
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

      <h2 className="mt-10 text-lg font-semibold">Lernpfad</h2>
      <p className="mb-4 text-xs text-zinc-500">
        Klicke ein <span className="text-blue-400">verfügbares</span> Modul an. Gesperrte
        Module brauchen erst ihre Voraussetzungen.
      </p>
      <div className="rounded-xl border border-zinc-800 bg-zinc-950 p-4">
        <SkillTree modules={cur.modules} />
      </div>

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
