"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  deleteVaultKey,
  getDataProviders,
  getDataBars,
  getVaultStatus,
  initVault,
  lockVault,
  setVaultKey,
  unlockVault,
  type DataBarsResponse,
  type DataProvidersResponse,
  type KnownService,
  type VaultStatus,
} from "@/lib/api";
import { useMode } from "@/lib/mode";

const cls = (...x: (string | false | undefined)[]) => x.filter(Boolean).join(" ");

export default function SettingsPage() {
  const [status, setStatus] = useState<VaultStatus | null>(null);
  const [providers, setProviders] = useState<DataProvidersResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const [s, p] = await Promise.all([getVaultStatus(), getDataProviders()]);
      setStatus(s);
      setProviders(p);
    } catch (e) {
      setError(String(e));
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const flash = (m: string) => {
    setNote(m);
    setTimeout(() => setNote(null), 2500);
  };

  return (
    <main className="mx-auto max-w-4xl px-8 py-8">
      <header className="mb-6">
        <h1 className="flex items-center gap-2 text-xl font-semibold tracking-tight">
          <span className="inline-block h-2.5 w-2.5 rounded-sm bg-sky-400" />
          Einstellungen
        </h1>
        <p className="mt-1 max-w-2xl text-sm text-zinc-400">
          BYOK-Schlüsseltresor (Master-Passwort, AES-256/Fernet, verschlüsselt at-rest),
          Daten-Provider und der globale Simple/Developer-Modus.
        </p>
      </header>

      {error && (
        <div className="mb-5 rounded-lg border border-red-700/60 bg-red-950/40 px-4 py-3 text-sm text-red-300">
          {error}
        </div>
      )}
      {note && (
        <div className="mb-5 rounded-lg border border-emerald-700/50 bg-emerald-950/30 px-4 py-2.5 text-sm text-emerald-300">
          {note}
        </div>
      )}

      <VaultSection status={status} onChange={refresh} flash={flash} setError={setError} />
      {status?.unlocked && (
        <KeysSection status={status} onChange={refresh} flash={flash} setError={setError} />
      )}
      <ProvidersSection providers={providers} unlocked={!!status?.unlocked} />
      <ModeSection />
    </main>
  );
}

function Card({ title, desc, children }: { title: string; desc?: string; children: React.ReactNode }) {
  return (
    <section className="mb-6 rounded-xl border border-zinc-800 bg-zinc-900/40 p-5">
      <div className="mb-4">
        <h2 className="text-sm font-semibold text-zinc-100">{title}</h2>
        {desc && <p className="mt-0.5 text-xs text-zinc-500">{desc}</p>}
      </div>
      {children}
    </section>
  );
}

// ── vault lifecycle (init / unlock / lock) ───────────────────────────────────
function VaultSection({
  status,
  onChange,
  flash,
  setError,
}: {
  status: VaultStatus | null;
  onChange: () => Promise<void>;
  flash: (m: string) => void;
  setError: (s: string | null) => void;
}) {
  const [pw, setPw] = useState("");
  const [pw2, setPw2] = useState("");
  const [busy, setBusy] = useState(false);

  if (!status) return <Card title="Schlüsseltresor">Lade …</Card>;

  const run = async (fn: () => Promise<VaultStatus>, ok: string) => {
    setBusy(true);
    setError(null);
    try {
      const r = await fn();
      if (!r.ok) throw new Error(r.error ?? "Fehler");
      setPw("");
      setPw2("");
      flash(ok);
      await onChange();
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  };

  if (!status.vault_exists) {
    const mismatch = pw2.length > 0 && pw !== pw2;
    return (
      <Card title="Schlüsseltresor anlegen" desc="Wähle ein Master-Passwort. Es verschlüsselt alle Keys und wird nirgends gespeichert — ohne dieses Passwort sind die Keys nicht wiederherstellbar.">
        <div className="flex flex-wrap items-end gap-3">
          <Field label="Master-Passwort" type="password" value={pw} onChange={setPw} />
          <Field label="Wiederholen" type="password" value={pw2} onChange={setPw2} />
          <button
            disabled={busy || !pw || pw !== pw2}
            onClick={() => run(() => initVault(pw), "Tresor angelegt & entsperrt.")}
            className={btn(!busy && !!pw && pw === pw2)}
          >
            Tresor anlegen
          </button>
        </div>
        {mismatch && <p className="mt-2 text-xs text-red-400">Passwörter stimmen nicht überein.</p>}
      </Card>
    );
  }

  if (!status.unlocked) {
    return (
      <Card title="Tresor entsperren" desc="Gib dein Master-Passwort ein. Die Keys werden für diese Session in den Speicher entschlüsselt.">
        <div className="flex flex-wrap items-end gap-3">
          <Field label="Master-Passwort" type="password" value={pw} onChange={setPw} />
          <button
            disabled={busy || !pw}
            onClick={() => run(() => unlockVault(pw), "Tresor entsperrt.")}
            className={btn(!busy && !!pw)}
          >
            Entsperren
          </button>
        </div>
      </Card>
    );
  }

  return (
    <Card title="Schlüsseltresor" desc="Entsperrt — die Keys sind für diese Session aktiv.">
      <div className="flex items-center justify-between">
        <span className="inline-flex items-center gap-2 text-sm text-emerald-300">
          <span className="h-2 w-2 rounded-full bg-emerald-400" />
          Entsperrt · {status.services_set.length} Schlüssel gespeichert
        </span>
        <button
          disabled={busy}
          onClick={() => run(() => lockVault(), "Tresor gesperrt.")}
          className="rounded-md border border-zinc-700 bg-zinc-800/50 px-3 py-1.5 text-xs text-zinc-300 hover:bg-zinc-800"
        >
          Sperren
        </button>
      </div>
    </Card>
  );
}

// ── per-service key management ───────────────────────────────────────────────
function KeysSection({
  status,
  onChange,
  flash,
  setError,
}: {
  status: VaultStatus;
  onChange: () => Promise<void>;
  flash: (m: string) => void;
  setError: (s: string | null) => void;
}) {
  const groups = useMemo(() => {
    const by: Record<string, KnownService[]> = {};
    for (const k of status.known) (by[k.group] ??= []).push(k);
    return by;
  }, [status.known]);

  return (
    <Card title="API-Schlüssel (BYOK)" desc="Werte werden nie zurückgegeben — nur der Gesetzt-Status ist sichtbar. Ein gesetzter Key überschreibt env/Keyfile sofort (z.B. Gemini für den Commander).">
      {Object.entries(groups).map(([group, items]) => (
        <div key={group} className="mb-5 last:mb-0">
          <div className="mb-2 text-[10px] font-semibold uppercase tracking-widest text-zinc-500">{group}</div>
          <div className="space-y-2">
            {items.map((k) => (
              <KeyRow key={k.service} k={k} onChange={onChange} flash={flash} setError={setError} />
            ))}
          </div>
        </div>
      ))}
    </Card>
  );
}

function KeyRow({
  k,
  onChange,
  flash,
  setError,
}: {
  k: KnownService;
  onChange: () => Promise<void>;
  flash: (m: string) => void;
  setError: (s: string | null) => void;
}) {
  const [val, setVal] = useState("");
  const [busy, setBusy] = useState(false);

  const save = async () => {
    if (!val) return;
    setBusy(true);
    setError(null);
    try {
      const r = await setVaultKey(k.service, val);
      if (!r.ok) throw new Error(r.error ?? "Fehler");
      setVal("");
      flash(`${k.label} gespeichert.`);
      await onChange();
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  };

  const remove = async () => {
    setBusy(true);
    setError(null);
    try {
      await deleteVaultKey(k.service);
      flash(`${k.label} entfernt.`);
      await onChange();
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex flex-wrap items-center gap-2 rounded-lg border border-zinc-800 bg-zinc-950/40 px-3 py-2">
      <div className="min-w-[180px] flex-1">
        <div className="flex items-center gap-2 text-sm text-zinc-200">
          <span className={cls("h-1.5 w-1.5 rounded-full", k.set ? "bg-emerald-400" : "bg-zinc-700")} />
          {k.label}
          <code className="text-[10px] text-zinc-600">{k.service}</code>
        </div>
      </div>
      <input
        type="password"
        value={val}
        placeholder={k.set ? "•••• gesetzt — neu eingeben zum Ersetzen" : "Key einfügen"}
        onChange={(e) => setVal(e.target.value)}
        onKeyDown={(e) => e.key === "Enter" && save()}
        className="min-w-[200px] flex-1 rounded border border-zinc-700 bg-zinc-900 px-2.5 py-1.5 font-mono text-xs text-zinc-100 placeholder:text-zinc-600"
      />
      <button disabled={busy || !val} onClick={save} className={btn(!busy && !!val, "sm")}>
        Speichern
      </button>
      {k.set && (
        <button
          disabled={busy}
          onClick={remove}
          className="rounded-md border border-red-800/60 bg-red-950/30 px-2.5 py-1.5 text-xs text-red-300 hover:bg-red-950/60"
        >
          Löschen
        </button>
      )}
    </div>
  );
}

// ── data providers + live Alpaca test ───────────────────────────────────────
function ProvidersSection({
  providers,
  unlocked,
}: {
  providers: DataProvidersResponse | null;
  unlocked: boolean;
}) {
  const [symbol, setSymbol] = useState("AAPL");
  const [provider, setProvider] = useState("alpaca");
  const [result, setResult] = useState<DataBarsResponse | null>(null);
  const [busy, setBusy] = useState(false);

  const test = async () => {
    setBusy(true);
    setResult(null);
    try {
      setResult(await getDataBars({ symbol, provider, timeframe: "1Day", limit: 5 }));
    } catch (e) {
      setResult({ ok: false, error: String(e) } as DataBarsResponse);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card title="Daten-Provider" desc="Vereinheitlichte Datenschicht: yfinance (frei) + Alpaca (BYOK). Verbindung testen, sobald die Alpaca-Keys im Tresor liegen.">
      <div className="mb-4 space-y-2">
        {(providers?.providers ?? []).map((p) => (
          <div key={p.provider} className="flex items-center gap-2 text-sm">
            <span className={cls("h-2 w-2 rounded-full", p.available ? "bg-emerald-400" : "bg-amber-400")} />
            <span className="text-zinc-200">{p.label}</span>
            <code className="text-[10px] text-zinc-600">{p.provider}</code>
            <span className={cls("text-xs", p.available ? "text-emerald-400/80" : "text-amber-400/80")}>
              {p.available ? "bereit" : p.reason}
            </span>
          </div>
        ))}
      </div>

      <div className="flex flex-wrap items-end gap-2 border-t border-zinc-800 pt-4">
        <label className="flex flex-col gap-1 text-xs text-zinc-400">
          Provider
          <select
            value={provider}
            onChange={(e) => setProvider(e.target.value)}
            className="rounded border border-zinc-700 bg-zinc-900 px-2 py-1.5 text-zinc-100"
          >
            {(providers?.providers ?? []).map((p) => (
              <option key={p.provider} value={p.provider}>
                {p.label}
              </option>
            ))}
          </select>
        </label>
        <Field label="Symbol" value={symbol} onChange={setSymbol} />
        <button disabled={busy} onClick={test} className={btn(!busy)}>
          {busy ? "Teste …" : "Verbindung testen"}
        </button>
        {provider === "alpaca" && !unlocked && (
          <span className="text-xs text-amber-400/80">Tresor entsperren + Alpaca-Keys setzen</span>
        )}
      </div>

      {result && (
        <div
          className={cls(
            "mt-3 rounded-lg border px-3 py-2 text-xs",
            result.ok ? "border-emerald-700/50 bg-emerald-950/20 text-emerald-200" : "border-red-800/60 bg-red-950/30 text-red-300",
          )}
        >
          {result.ok ? (
            <>
              ✓ {result.count} Bars für <b>{result.symbol}</b> via {result.provider} ({result.start} … {result.end});
              letzter Close{" "}
              <span className="font-mono">{result.bars.at(-1)?.close?.toFixed(2)}</span>
            </>
          ) : (
            <>✗ {result.error}</>
          )}
        </div>
      )}
    </Card>
  );
}

// ── global mode ──────────────────────────────────────────────────────────────
function ModeSection() {
  const { mode, setMode } = useMode();
  return (
    <Card title="Oberflächen-Modus" desc="Simple zeigt nur die Entscheidungs-Screens (Swarm, Live Book, Seasonal, COT, Charts). Developer schaltet alle Forschungs- und Desk-Werkzeuge frei.">
      <div className="flex gap-2">
        {(["simple", "developer"] as const).map((m) => (
          <button
            key={m}
            onClick={() => setMode(m)}
            className={cls(
              "rounded-lg border px-4 py-2 text-sm capitalize transition-colors",
              mode === m
                ? "border-sky-600/60 bg-sky-500/10 text-sky-200"
                : "border-zinc-700 bg-zinc-900/50 text-zinc-400 hover:bg-zinc-800",
            )}
          >
            {m === "simple" ? "Simple" : "Developer"}
          </button>
        ))}
      </div>
    </Card>
  );
}

// ── small controls ───────────────────────────────────────────────────────────
function Field({
  label,
  value,
  onChange,
  type = "text",
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  type?: string;
}) {
  return (
    <label className="flex flex-col gap-1 text-xs text-zinc-400">
      {label}
      <input
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-44 rounded border border-zinc-700 bg-zinc-900 px-2.5 py-1.5 text-sm text-zinc-100"
      />
    </label>
  );
}

const btn = (enabled: boolean, size: "sm" | "md" = "md") =>
  cls(
    "rounded-md font-medium transition-colors",
    size === "sm" ? "px-2.5 py-1.5 text-xs" : "px-4 py-2 text-sm",
    enabled ? "bg-sky-600 text-white hover:bg-sky-500" : "cursor-not-allowed bg-zinc-800 text-zinc-500",
  );
