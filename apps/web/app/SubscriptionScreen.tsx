"use client";

import { useState } from "react";
import { openCheckout, useLicense } from "@/lib/license";

/**
 * Full-screen "hard wall" shown when the gate status is EXPIRED. Dark, elegant,
 * and the *only* thing rendered — the dashboard behind it is fully unmounted.
 *
 * Two paths out: subscribe (opens the external checkout) or paste an existing
 * license key and activate it (validated against Lemon Squeezy by the Rust backend).
 */
export default function SubscriptionScreen() {
  const { activate } = useLicense();
  const [key, setKey] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onActivate(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    const res = await activate(key);
    setSubmitting(false);
    if (!res.ok) setError(res.error ?? "Aktivierung fehlgeschlagen.");
    // On success the provider flips to LICENSED and this screen unmounts automatically.
  }

  return (
    <main className="fixed inset-0 z-[100] flex items-center justify-center overflow-y-auto bg-zinc-950 px-6 py-12">
      {/* ambient glow */}
      <div className="pointer-events-none absolute inset-0 overflow-hidden">
        <div className="absolute -top-40 left-1/2 h-[36rem] w-[36rem] -translate-x-1/2 rounded-full bg-emerald-500/10 blur-[120px]" />
        <div className="absolute bottom-[-12rem] right-[-8rem] h-[28rem] w-[28rem] rounded-full bg-indigo-500/10 blur-[120px]" />
      </div>

      <div className="relative w-full max-w-md">
        {/* brand */}
        <div className="mb-8 flex items-center justify-center gap-2">
          <span className="inline-block h-2.5 w-2.5 rounded-sm bg-emerald-400" />
          <span className="text-sm font-semibold tracking-tight text-zinc-200">Quant OS Pro</span>
        </div>

        <div className="rounded-2xl border border-zinc-800 bg-zinc-900/60 p-8 shadow-2xl shadow-black/50 backdrop-blur">
          <h1 className="text-center text-2xl font-semibold tracking-tight text-zinc-100">
            Deine Testphase ist abgelaufen
          </h1>
          <p className="mt-3 text-center text-sm leading-relaxed text-zinc-400">
            Abonniere <span className="text-zinc-200">Quant OS Pro</span>, um deine
            Handelsstrategien und den Agentenschwarm wieder zu aktivieren.
          </p>

          {/* primary CTA → external checkout */}
          <button
            onClick={() => void openCheckout()}
            className="mt-6 flex w-full items-center justify-center gap-2 rounded-lg bg-emerald-500 px-4 py-2.5 text-sm font-semibold text-emerald-950 transition-colors hover:bg-emerald-400"
          >
            Quant OS Pro abonnieren
            <svg className="h-3.5 w-3.5" viewBox="0 0 16 16" fill="none">
              <path d="M6 3l5 5-5 5" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </button>

          {/* divider */}
          <div className="my-6 flex items-center gap-3 text-[11px] uppercase tracking-widest text-zinc-600">
            <span className="h-px flex-1 bg-zinc-800" />
            Lizenz vorhanden?
            <span className="h-px flex-1 bg-zinc-800" />
          </div>

          {/* license key activation */}
          <form onSubmit={onActivate} className="space-y-3">
            <input
              type="text"
              value={key}
              onChange={(e) => setKey(e.target.value)}
              placeholder="Lizenzschlüssel einfügen (XXXXXXXX-XXXX-…)"
              autoCapitalize="off"
              autoCorrect="off"
              spellCheck={false}
              className="w-full rounded-lg border border-zinc-800 bg-zinc-950/80 px-3 py-2.5 font-mono text-sm text-zinc-100 placeholder:text-zinc-600 focus:border-emerald-500/60 focus:outline-none focus:ring-1 focus:ring-emerald-500/40"
            />
            <button
              type="submit"
              disabled={submitting || key.trim().length === 0}
              className="w-full rounded-lg border border-zinc-700 bg-zinc-800/80 px-4 py-2.5 text-sm font-semibold text-zinc-100 transition-colors hover:bg-zinc-700 disabled:cursor-not-allowed disabled:opacity-40"
            >
              {submitting ? "Wird aktiviert…" : "Aktivieren"}
            </button>
          </form>

          {error && (
            <p className="mt-3 rounded-lg border border-red-900/60 bg-red-950/40 px-3 py-2 text-center text-xs text-red-300">
              {error}
            </p>
          )}
        </div>

        <p className="mt-6 text-center text-[11px] leading-relaxed text-zinc-600">
          Dein Abonnement schaltet alle Module frei: Wetter-Radar, COT-Positionierung,
          Saisonalität, den Agentenschwarm und das Risiko-Desk.
        </p>
      </div>
    </main>
  );
}
