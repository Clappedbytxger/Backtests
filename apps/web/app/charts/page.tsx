"use client";

import { useCallback, useState } from "react";

import Toolbar from "./Toolbar";
import TerminalChart, { type VisibleRange } from "./TerminalChart";
import { useChartData } from "./useChartData";

// Only fetch a footprint when the user is zoomed in enough to read it.
const FOOTPRINT_MAX_BARS = 180;

export default function ChartsPage() {
  const d = useChartData();
  const [showProfile, setShowProfile] = useState(true);
  const [showDelta, setShowDelta] = useState(false);
  const [footprintCells, setFootprintCells] = useState(false);

  const onVisibleRange = useCallback(
    (r: VisibleRange) => {
      if (d.instrument?.footprint && r.bars <= FOOTPRINT_MAX_BARS) {
        d.loadFootprint(r.fromSec, r.toSec);
      } else {
        d.clearFootprint();
      }
    },
    [d.instrument, d.loadFootprint, d.clearFootprint],
  );

  const status = d.loading
    ? "loading…"
    : d.loadingMore
      ? "loading history…"
      : d.instrument
        ? `${d.candles.length} bars · ${d.footprint.length} fp clusters`
        : "";

  const fitKey = `${d.instrument?.ticker ?? ""}|${d.timeframe}|${d.rth}|${d.adjust}`;

  return (
    <main className="flex h-[calc(100vh-61px)] w-full flex-col gap-2 p-3">
      <Toolbar
        instruments={d.instruments}
        instrument={d.instrument}
        onSelect={d.setInstrument}
        timeframe={d.timeframe}
        onTimeframe={d.setTimeframe}
        rth={d.rth}
        onRth={d.setRth}
        adjust={d.adjust}
        onAdjust={d.setAdjust}
        showProfile={showProfile}
        onToggleProfile={() => setShowProfile((v) => !v)}
        showDelta={showDelta}
        onToggleDelta={() => setShowDelta((v) => !v)}
        footprintCells={footprintCells}
        onToggleFootprintCells={() => setFootprintCells((v) => !v)}
        status={status}
      />

      {d.error && (
        <div className="rounded-lg border border-red-900 bg-red-950/40 px-3 py-2 text-sm text-red-300">
          {d.error} — is the API running?{" "}
          <code className="text-red-200">uvicorn apps.api.main:app --port 8000</code>
        </div>
      )}

      <div className="relative min-h-0 flex-1 overflow-hidden rounded-xl border border-white/10 bg-[#0a0a0a]">
        {d.instrument && (
          <TerminalChart
            candles={d.candles}
            footprint={d.footprint}
            showProfile={showProfile}
            showDelta={showDelta}
            footprintCells={footprintCells}
            fitKey={fitKey}
            onReachLeft={d.loadMorePast}
            onVisibleRange={onVisibleRange}
          />
        )}
        {d.loading && (
          <div className="absolute inset-0 grid place-items-center text-sm text-zinc-500">
            Loading {d.instrument?.ticker}…
          </div>
        )}
        {!d.loading && d.instrument && !d.candles.length && (
          <div className="absolute inset-0 grid place-items-center text-sm text-zinc-500">
            No data for this window.
          </div>
        )}
      </div>

      <div className="flex items-center justify-between font-mono text-[11px] text-zinc-600">
        <span>
          {d.instrument
            ? `${d.instrument.ticker} · ${d.timeframe} · ${d.instrument.asset_class}`
            : "—"}
        </span>
        <span>Volume-by-price reconstructed from OHLCV · delta = tick-rule approximation</span>
      </div>
    </main>
  );
}
