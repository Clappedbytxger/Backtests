"use client";

import { useMemo, useState } from "react";
import { Slider, VizFrame } from "./controls";

const T = 24; // total time periods
const TEST = 3; // OOS length per window

type Mode = "rolling" | "expanding";
type Cell = "unused" | "train" | "test";

/**
 * Walk-forward analysis. Time runs left→right. Each row is one fold: the model is fit on
 * the TRAIN block (grey) and scored only on the OOS TEST block (green) that immediately
 * follows — then the window steps forward. ROLLING keeps a fixed look-back; EXPANDING
 * uses all history so far. Unlike CPCV, every test point lies strictly in the future of its
 * train: this is the honest, tradable path (and why it usually scores below CPCV).
 */
export default function WalkForwardSplits() {
  const [mode, setMode] = useState<Mode>("rolling");
  const [trainLen, setTrainLen] = useState(6);

  const folds = useMemo(() => {
    const out: Cell[][] = [];
    for (let testStart = trainLen; testStart + TEST <= T; testStart += TEST) {
      const trainStart = mode === "rolling" ? testStart - trainLen : 0;
      const cells: Cell[] = [];
      for (let i = 0; i < T; i++) {
        if (i >= testStart && i < testStart + TEST) cells.push("test");
        else if (i >= trainStart && i < testStart) cells.push("train");
        else cells.push("unused");
      }
      out.push(cells);
    }
    return out;
  }, [mode, trainLen]);

  const COLOR: Record<Cell, string> = {
    unused: "#18181b",
    train: "#3f3f46",
    test: "#22c55e",
  };

  return (
    <VizFrame
      caption={
        <>
          {folds.length} Folds, je {TEST} Perioden OOS. <b>{mode === "rolling" ? "Rolling" : "Expanding"}</b>:
          das Train-Fenster {mode === "rolling" ? "gleitet mit fester Länge mit" : "wächst über die ganze Historie"}.
          Jeder grüne Test liegt strikt nach seinem Train — kein Leakage, der ehrliche Pfad. Genau dieser
          OOS-Schnitt ist typischerweise schwächer als der CPCV-Stitch (0060: +0,81 → +0,38).
        </>
      }
    >
      <div className="mb-3 flex flex-wrap items-end gap-6">
        <div className="flex gap-1 text-xs">
          {(["rolling", "expanding"] as Mode[]).map((mo) => (
            <button
              key={mo}
              onClick={() => setMode(mo)}
              className={`rounded border px-2 py-1 ${mode === mo ? "border-blue-500 bg-blue-500/10 text-blue-200" : "border-zinc-700 text-zinc-400"}`}
            >
              {mo === "rolling" ? "Rolling" : "Expanding"}
            </button>
          ))}
        </div>
        <Slider label="Train-Länge" value={trainLen} min={3} max={12} step={1} onChange={setTrainLen} fmt={(v) => String(Math.round(v))} />
        <div className="flex items-end gap-3 text-xs text-zinc-400">
          <span className="flex items-center gap-1.5"><span className="h-3 w-3 rounded-sm" style={{ background: COLOR.train }} />Train (IS)</span>
          <span className="flex items-center gap-1.5"><span className="h-3 w-3 rounded-sm" style={{ background: COLOR.test }} />Test (OOS)</span>
        </div>
      </div>
      <div className="space-y-1">
        <div className="flex gap-0.5 pl-12 text-[10px] text-zinc-600">
          {Array.from({ length: T }, (_, i) => (
            <div key={i} className="flex-1 text-center">{i % 3 === 0 ? i : ""}</div>
          ))}
        </div>
        {folds.map((cells, ri) => (
          <div key={ri} className="flex items-center gap-0.5">
            <div className="w-11 shrink-0 text-right font-mono text-[10px] text-zinc-600">F{ri + 1}</div>
            {cells.map((c, ci) => (
              <div key={ci} className="h-5 flex-1 rounded-sm" style={{ background: COLOR[c] }} title={c} />
            ))}
          </div>
        ))}
      </div>
    </VizFrame>
  );
}
