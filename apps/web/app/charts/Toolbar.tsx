"use client";

import { useMemo, useRef, useState } from "react";

import type { Instrument } from "@/lib/api";

const ALL_TF = ["1m", "5m", "15m", "1h", "4h", "1D"];

const CLASS_DOT: Record<string, string> = {
  futures: "bg-cyan-400",
  equities: "bg-emerald-400",
  crypto: "bg-amber-400",
};

interface Props {
  instruments: Instrument[];
  instrument: Instrument | null;
  onSelect: (i: Instrument) => void;
  timeframe: string;
  onTimeframe: (tf: string) => void;
  rth: boolean;
  onRth: (v: boolean) => void;
  adjust: boolean;
  onAdjust: (v: boolean) => void;
  showProfile: boolean;
  onToggleProfile: () => void;
  showDelta: boolean;
  onToggleDelta: () => void;
  footprintCells: boolean;
  onToggleFootprintCells: () => void;
  status?: string;
}

export default function Toolbar(props: Props) {
  const { instrument } = props;
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const blurTimer = useRef<number | undefined>(undefined);

  const matches = useMemo(() => {
    const q = query.trim().toUpperCase();
    const list = q
      ? props.instruments.filter((i) => i.ticker.toUpperCase().includes(q))
      : props.instruments;
    return list.slice(0, 60);
  }, [query, props.instruments]);

  const pick = (i: Instrument) => {
    props.onSelect(i);
    setQuery("");
    setOpen(false);
  };

  const isCrypto = instrument?.asset_class === "crypto";

  return (
    <div className="relative z-30 flex flex-wrap items-center gap-2 rounded-xl border border-white/10 bg-zinc-900/70 px-3 py-2 backdrop-blur supports-[backdrop-filter]:bg-zinc-900/50">
      {/* ticker search */}
      <div className="relative">
        <input
          value={open ? query : (instrument?.ticker ?? "")}
          onChange={(e) => {
            setQuery(e.target.value);
            setOpen(true);
          }}
          onFocus={() => {
            setQuery("");
            setOpen(true);
          }}
          onBlur={() => {
            blurTimer.current = window.setTimeout(() => setOpen(false), 150);
          }}
          placeholder="Search ticker…"
          spellCheck={false}
          className="w-40 rounded-lg border border-white/10 bg-black/40 px-3 py-1.5 font-mono text-sm text-zinc-100 outline-none placeholder:text-zinc-600 focus:border-cyan-500/60"
        />
        {open && matches.length > 0 && (
          <ul
            className="absolute z-30 mt-1 max-h-72 w-64 overflow-auto rounded-lg border border-white/10 bg-zinc-950/95 p-1 shadow-2xl backdrop-blur"
            onMouseEnter={() => window.clearTimeout(blurTimer.current)}
          >
            {matches.map((i) => (
              <li key={i.ticker}>
                <button
                  onMouseDown={(e) => {
                    e.preventDefault();
                    pick(i);
                  }}
                  className={`flex w-full items-center justify-between rounded-md px-2 py-1.5 text-left hover:bg-white/5 ${
                    i.ticker === instrument?.ticker ? "bg-white/5" : ""
                  }`}
                >
                  <span className="flex items-center gap-2">
                    <span className={`h-1.5 w-1.5 rounded-full ${CLASS_DOT[i.asset_class] ?? "bg-zinc-500"}`} />
                    <span className="font-mono text-sm text-zinc-100">{i.ticker}</span>
                  </span>
                  <span className="flex items-center gap-2 font-mono text-[10px] text-zinc-500">
                    <span>{i.asset_class}</span>
                    {i.footprint && <span className="text-cyan-400/80">FP</span>}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>

      {/* timeframe segmented control */}
      <div className="flex overflow-hidden rounded-lg border border-white/10">
        {ALL_TF.map((tf) => {
          const enabled = instrument?.available_tfs.includes(tf) ?? false;
          const active = tf === props.timeframe;
          return (
            <button
              key={tf}
              disabled={!enabled}
              onClick={() => props.onTimeframe(tf)}
              className={`px-2.5 py-1.5 font-mono text-xs transition-colors ${
                active
                  ? "bg-cyan-500/20 text-cyan-300"
                  : enabled
                    ? "text-zinc-400 hover:bg-white/5 hover:text-zinc-100"
                    : "cursor-not-allowed text-zinc-700"
              }`}
            >
              {tf}
            </button>
          );
        })}
      </div>

      <Toggle active={props.rth} disabled={isCrypto} onClick={() => props.onRth(!props.rth)} title={isCrypto ? "24h market" : "Regular trading hours only"}>
        RTH
      </Toggle>
      <Toggle
        active={props.adjust}
        disabled={instrument?.asset_class !== "equities"}
        onClick={() => props.onAdjust(!props.adjust)}
        title={
          instrument?.asset_class === "equities"
            ? "Split-adjust prices (TradingView parity); off = raw exchange prints"
            : "Split adjustment only applies to stocks"
        }
      >
        ADJ
      </Toggle>
      <Toggle active={props.showProfile} onClick={props.onToggleProfile}>
        Profile
      </Toggle>
      <Toggle active={props.showDelta} onClick={props.onToggleDelta}>
        Delta
      </Toggle>
      <Toggle
        active={props.footprintCells}
        disabled={!instrument?.footprint}
        onClick={props.onToggleFootprintCells}
        title="Per-candle bid×ask footprint (zoom in to read)"
      >
        FP
      </Toggle>

      {/* approx badge */}
      {instrument?.footprint ? (
        <span
          title="Bid/ask delta is a tick-rule approximation from OHLCV — not real trade flow."
          className="rounded-md border border-amber-500/30 bg-amber-950/40 px-2 py-1 font-mono text-[10px] uppercase tracking-wider text-amber-300"
        >
          approx · tick-rule
        </span>
      ) : (
        instrument && (
          <span className="rounded-md border border-white/10 bg-white/5 px-2 py-1 font-mono text-[10px] uppercase tracking-wider text-zinc-500">
            no footprint · {instrument.native_tf}
          </span>
        )
      )}

      <div className="ml-auto font-mono text-[11px] text-zinc-500">{props.status}</div>
    </div>
  );
}

function Toggle({
  active,
  disabled,
  onClick,
  title,
  children,
}: {
  active: boolean;
  disabled?: boolean;
  onClick: () => void;
  title?: string;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      title={title}
      className={`rounded-lg border px-2.5 py-1.5 font-mono text-xs transition-colors ${
        disabled
          ? "cursor-not-allowed border-white/5 text-zinc-700"
          : active
            ? "border-cyan-500/40 bg-cyan-500/15 text-cyan-300"
            : "border-white/10 text-zinc-400 hover:bg-white/5 hover:text-zinc-100"
      }`}
    >
      {children}
    </button>
  );
}
