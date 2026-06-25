"use client";

import { useMemo, useState } from "react";
import { CartesianGrid, Line, LineChart, ReferenceDot, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { AXIS, GRID, Slider, TOOLTIP, VizFrame } from "./controls";

const S0 = 100; // front-ish spot level
const N_CONTRACTS = 7; // months out

/**
 * Futures term structure & roll yield. The curve price at month m is S0·exp(slope·m/12).
 * slope>0 = CONTANGO (upward), slope<0 = BACKWARDATION (downward). A long roller earns the
 * roll yield = (P_front − P_second)/P_front annualised: positive in backwardation (you buy
 * cheap-far, it rolls UP to spot), negative in contango. This sign is the structural carry
 * premium that the 0048 ranking goes long/short on.
 */
export default function RollYieldCurve() {
  const [slope, setSlope] = useState(-0.15); // annualised; negative = backwardation

  const { curve, rollYield } = useMemo(() => {
    const price = (m: number) => S0 * Math.exp((slope * m) / 12);
    const curve = Array.from({ length: N_CONTRACTS }, (_, m) => ({ m, price: +price(m + 1).toFixed(2) }));
    const front = price(1), second = price(2);
    const rollYield = ((front - second) / front) * 12; // annualised (monthly spacing)
    return { curve, rollYield };
  }, [slope]);

  const contango = slope > 0;

  return (
    <VizFrame
      caption={
        <>
          {contango ? "Contango" : "Backwardation"} (Slope {(slope * 100).toFixed(0)} % p.a.). Roll-Yield für
          einen Long ={" "}
          <b className={rollYield >= 0 ? "text-emerald-400" : "text-red-400"}>{(rollYield * 100).toFixed(1)} % p.a.</b>{" "}
          — {rollYield >= 0
            ? "Backwardation zahlt den Roller (kauf billig-fern, rollt hoch zum Spot)."
            : "Contango kostet den Roller (kauf teuer-fern, rollt runter)."}{" "}
          Genau dieses Vorzeichen ranked das Carry-Portfolio (0048): long Backwardation, short Contango.
        </>
      }
    >
      <div className="mb-3 flex flex-wrap gap-6">
        <Slider label="Kurvenform (Slope p.a.)" value={slope} min={-0.4} max={0.4} step={0.01} onChange={setSlope} fmt={(v) => `${(v * 100).toFixed(0)}%`} />
      </div>
      <ResponsiveContainer width="100%" height={230}>
        <LineChart data={curve}>
          <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
          <XAxis dataKey="m" tick={AXIS} label={{ value: "Kontrakt (Monate)", fill: "#a1a1aa", fontSize: 10, dy: 12 }} tickFormatter={(v) => `M${v + 1}`} />
          <YAxis tick={AXIS} width={44} domain={["auto", "auto"]} />
          <Tooltip contentStyle={TOOLTIP} />
          <Line dataKey="price" stroke={contango ? "#ef4444" : "#22c55e"} strokeWidth={2} dot={{ r: 3 }} isAnimationActive={false} />
          <ReferenceDot x={0} y={curve[0].price} r={5} fill="#eab308" stroke="none" />
          <ReferenceDot x={1} y={curve[1].price} r={5} fill="#3b82f6" stroke="none" />
        </LineChart>
      </ResponsiveContainer>
      <div className="mt-1 flex gap-4 text-[11px] text-zinc-500">
        <span className="flex items-center gap-1"><span className="h-2 w-2 rounded-full bg-amber-500" /> Front (M1)</span>
        <span className="flex items-center gap-1"><span className="h-2 w-2 rounded-full bg-blue-500" /> Second (M2)</span>
      </div>
    </VizFrame>
  );
}
