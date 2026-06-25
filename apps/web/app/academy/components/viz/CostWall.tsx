"use client";

import { useMemo, useState } from "react";
import { CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { AXIS, GRID, Slider, TOOLTIP, VizFrame } from "./controls";

const TRADES = 250; // ~ one year of daily trades

/**
 * The cost wall. Each trade earns a tiny GROSS edge (bps) but pays a fixed round-trip COST
 * (bps). Net per trade = gross − cost. Trading more only compounds the sign: if gross < cost,
 * every extra trade digs the hole deeper. This is why a strong intraday signal (high
 * frequency, small edge) dies net-of-cost (0012-0015 crypto, 0038-0041 index, 0049).
 */
export default function CostWall() {
  const [gross, setGross] = useState(4); // bps per trade (gross edge)
  const [cost, setCost] = useState(6); // bps round-trip cost

  const { rows, net } = useMemo(() => {
    const net = gross - cost;
    const rows = Array.from({ length: TRADES + 1 }, (_, n) => ({
      n,
      grossPnl: +(n * gross).toFixed(1),
      netPnl: +(n * net).toFixed(1),
    }));
    return { rows, net };
  }, [gross, cost]);

  const annual = net * TRADES;

  return (
    <VizFrame
      caption={
        <>
          Brutto {gross} bps/Trade, Kosten {cost} bps RT ⇒ netto{" "}
          <b className={net >= 0 ? "text-emerald-400" : "text-red-400"}>{net >= 0 ? "+" : ""}{net.toFixed(1)} bps/Trade</b>{" "}
          ({annual >= 0 ? "+" : ""}{(annual / 100).toFixed(1)} % über {TRADES} Trades). Die graue Linie ist der
          Brutto-Edge, die farbige der Netto-Pfad. Liegt der Brutto-Edge <i>unter</i> der Kostenwand, gräbt
          jeder weitere Trade das Loch tiefer — der Grund, warum liquider Intraday-Richtungshandel netto tot ist.
        </>
      }
    >
      <div className="mb-3 flex flex-wrap gap-6">
        <Slider label="Brutto-Edge (bps/Trade)" value={gross} min={0} max={15} step={0.5} onChange={setGross} fmt={(v) => `${v.toFixed(1)}`} accent="accent-emerald-500" />
        <Slider label="Kosten (bps RT)" value={cost} min={0} max={20} step={0.5} onChange={setCost} fmt={(v) => `${v.toFixed(1)}`} accent="accent-red-500" />
      </div>
      <ResponsiveContainer width="100%" height={240}>
        <LineChart data={rows}>
          <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
          <XAxis dataKey="n" tick={AXIS} label={{ value: "Anzahl Trades", fill: "#a1a1aa", fontSize: 10, dy: 12 }} />
          <YAxis tick={AXIS} width={48} label={{ value: "kum. bps", angle: -90, position: "insideLeft", fill: "#a1a1aa", fontSize: 10 }} />
          <Tooltip contentStyle={TOOLTIP} />
          <ReferenceLine y={0} stroke="#52525b" />
          <Line dataKey="grossPnl" stroke="#52525b" dot={false} strokeWidth={1.5} strokeDasharray="5 4" isAnimationActive={false} />
          <Line dataKey="netPnl" stroke={net >= 0 ? "#22c55e" : "#ef4444"} dot={false} strokeWidth={2.5} isAnimationActive={false} />
        </LineChart>
      </ResponsiveContainer>
    </VizFrame>
  );
}
