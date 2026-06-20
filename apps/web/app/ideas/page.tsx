"use client";

import { useEffect, useState } from "react";
import { getIdeas, type Idea } from "@/lib/api";

export default function IdeasPage() {
  const [ideas, setIdeas] = useState<Idea[]>([]);
  const [exists, setExists] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getIdeas()
      .then((r) => {
        setIdeas(r.ideas);
        setExists(r.exists);
      })
      .catch((e) => setError(String(e)));
  }, []);

  if (error) return <main className="mx-auto max-w-6xl p-8 text-red-300">Error: {error}</main>;

  return (
    <main className="mx-auto max-w-6xl p-8">
      <h1 className="text-2xl font-semibold">Research Hub</h1>
      <p className="mt-1 text-sm text-zinc-400">
        {exists
          ? `${ideas.length} hypotheses from the ideas backlog`
          : "HYPOTHESES.csv not found in IDEAS_DIR — set ideas_dir in config.yaml"}
      </p>

      <table className="mt-6 w-full text-left text-sm">
        <thead className="text-zinc-400">
          <tr className="border-b border-zinc-800">
            <th className="py-2 pr-3 font-medium">ID</th>
            <th className="py-2 pr-3 font-medium">Title</th>
            <th className="py-2 pr-3 font-medium">Market</th>
            <th className="py-2 pr-3 font-medium">Category</th>
            <th className="py-2 pr-3 font-medium">Prio</th>
            <th className="py-2 pr-3 font-medium">Status</th>
          </tr>
        </thead>
        <tbody>
          {ideas.map((i) => (
            <tr key={i.ID} className="border-b border-zinc-900 align-top hover:bg-zinc-900/40">
              <td className="py-1.5 pr-3 font-mono text-zinc-400">{i.ID}</td>
              <td className="py-1.5 pr-3">
                {i.Titel}
                <div className="text-xs text-zinc-500">{i.Kernidee_kurz}</div>
              </td>
              <td className="py-1.5 pr-3 font-mono text-zinc-400">{i.Markt}</td>
              <td className="py-1.5 pr-3 text-zinc-400">{i.Kategorie}</td>
              <td className="py-1.5 pr-3">{i.Prioritaet}</td>
              <td className="py-1.5 pr-3">{i.Status}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </main>
  );
}
