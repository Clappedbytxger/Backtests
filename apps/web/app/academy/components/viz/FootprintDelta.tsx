"use client";

import { useMemo, useState } from "react";
import { gauss, rng, Slider, VizFrame } from "./controls";

const LEVELS = 15; // price levels in the cluster

/**
 * Footprint / volume cluster. For one bar, volume is split by price level into BID-initiated
 * (sellers hitting the bid) and ASK-initiated (buyers lifting the ask) trades. Delta =
 * ask − bid reveals who was aggressive. The POC (point of control) is the level with most
 * volume. The "Aggressor-Bias" slider shifts buying vs selling pressure — the read order-flow
 * traders chase. Note: from OHLCV the split is only a tick-rule APPROXIMATION (0-anchor memo).
 */
export default function FootprintDelta() {
  const [bias, setBias] = useState(0); // -1 sellers ... +1 buyers

  const { rows, pocIdx, totalDelta } = useMemo(() => {
    const r = rng(9);
    const mid = (LEVELS - 1) / 2;
    const rows = Array.from({ length: LEVELS }, (_, i) => {
      // total volume peaks near the middle (a normal-ish profile)
      const dist = Math.exp(-0.5 * ((i - mid) / 4) ** 2);
      const total = 40 + 260 * dist * (0.7 + 0.3 * Math.abs(gauss(r)));
      // split by aggressor: bias tilts the share toward ask (buyers) or bid (sellers)
      const askShare = 0.5 + 0.35 * bias + 0.08 * gauss(r);
      const ask = Math.max(0, total * Math.min(0.95, Math.max(0.05, askShare)));
      const bid = Math.max(0, total - ask);
      return { price: 100 + (LEVELS - 1 - i) * 0.25, bid, ask, total, delta: ask - bid };
    });
    const pocIdx = rows.reduce((best, r2, i, arr) => (r2.total > arr[best].total ? i : best), 0);
    const totalDelta = rows.reduce((s, r2) => s + r2.delta, 0);
    const maxSide = Math.max(...rows.map((r2) => Math.max(r2.bid, r2.ask)));
    rows.forEach((r2) => {
      (r2 as { bidPct?: number }).bidPct = (r2.bid / maxSide) * 100;
      (r2 as { askPct?: number }).askPct = (r2.ask / maxSide) * 100;
    });
    return { rows, pocIdx, totalDelta };
  }, [bias]);

  return (
    <VizFrame
      caption={
        <>
          Pro Preis-Level: <span className="text-red-400">Bid-Volumen</span> (Verkäufer treffen das Gebot,
          links) vs. <span className="text-emerald-400">Ask-Volumen</span> (Käufer heben den Brief, rechts).
          Delta = Ask − Bid. Gelb = POC (meistes Volumen). Gesamt-Delta ={" "}
          <b className={totalDelta >= 0 ? "text-emerald-400" : "text-red-400"}>{totalDelta >= 0 ? "+" : ""}{totalDelta.toFixed(0)}</b>{" "}
          ⇒ {totalDelta >= 0 ? "Käufer aggressiv" : "Verkäufer aggressiv"}. Aus OHLCV ist die Aufteilung nur
          eine Tick-Rule-Näherung.
        </>
      }
    >
      <div className="mb-3 flex flex-wrap gap-6">
        <Slider label="Aggressor-Bias (Verkäufer ↔ Käufer)" value={bias} min={-1} max={1} step={0.05} onChange={setBias} fmt={(v) => (v > 0.1 ? "Käufer" : v < -0.1 ? "Verkäufer" : "neutral")} width="w-56" />
      </div>
      <div className="space-y-0.5 font-mono text-[11px]">
        <div className="flex items-center text-zinc-500">
          <div className="flex-1 pr-2 text-right">Bid (Sell)</div>
          <div className="w-16 text-center">Preis</div>
          <div className="flex-1 pl-2">Ask (Buy)</div>
          <div className="w-12 text-right">Δ</div>
        </div>
        {rows.map((r2, i) => (
          <div key={i} className={`flex items-center ${i === pocIdx ? "rounded bg-amber-500/10" : ""}`}>
            <div className="flex flex-1 justify-end pr-2">
              <div className="h-3.5 rounded-l bg-red-500/70" style={{ width: `${(r2 as { bidPct?: number }).bidPct}%` }} />
            </div>
            <div className={`w-16 text-center ${i === pocIdx ? "text-amber-300" : "text-zinc-400"}`}>{r2.price.toFixed(2)}</div>
            <div className="flex flex-1 pl-2">
              <div className="h-3.5 rounded-r bg-emerald-500/70" style={{ width: `${(r2 as { askPct?: number }).askPct}%` }} />
            </div>
            <div className={`w-12 text-right ${r2.delta >= 0 ? "text-emerald-400" : "text-red-400"}`}>
              {r2.delta >= 0 ? "+" : ""}{r2.delta.toFixed(0)}
            </div>
          </div>
        ))}
      </div>
    </VizFrame>
  );
}
