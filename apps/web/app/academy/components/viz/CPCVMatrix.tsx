"use client";

import { useMemo, useState } from "react";
import { Slider, VizFrame } from "./controls";

const N = 10; // time groups along the x-axis

/** All k-subsets of {0..n-1}. */
function combinations(n: number, k: number): number[][] {
  const out: number[][] = [];
  const pick = (start: number, acc: number[]) => {
    if (acc.length === k) {
      out.push([...acc]);
      return;
    }
    for (let i = start; i < n; i++) pick(i + 1, [...acc, i]);
  };
  pick(0, []);
  return out;
}

type Cell = "train" | "test" | "purge";

/**
 * Combinatorial Purged Cross-Validation. Time is split into N equal groups. For each
 * way to choose k TEST groups (all C(N,k) combinations), the groups directly adjacent to
 * a test block are PURGED/embargoed so no label leaks across the boundary; the rest is
 * train. The grid makes visible why CPCV yields many overlapping paths — and why the
 * purge band is non-negotiable in time series.
 */
export default function CPCVMatrix() {
  const [k, setK] = useState(2);

  const { rows, nSplits } = useMemo(() => {
    const combos = combinations(N, k);
    const nSplits = combos.length;
    const shown = combos.slice(0, 14); // cap rows for legibility
    const rows = shown.map((testGroups) => {
      const testSet = new Set(testGroups);
      const cells: Cell[] = [];
      for (let i = 0; i < N; i++) {
        if (testSet.has(i)) cells.push("test");
        else if (testSet.has(i - 1) || testSet.has(i + 1)) cells.push("purge");
        else cells.push("train");
      }
      return cells;
    });
    return { rows, nSplits };
  }, [k]);

  const COLOR: Record<Cell, string> = {
    train: "#27272a",
    test: "#3b82f6",
    purge: "#f59e0b",
  };

  return (
    <VizFrame
      caption={
        <>
          N={N} Zeit-Gruppen, k={k} Test-Gruppen ⇒ <b>{nSplits} Splits</b> (alle Kombinationen).
          Blau = Test, Gelb = Purge/Embargo (gesperrt, damit kein Label über die Grenze leakt),
          Grau = Train. Mehr k ⇒ mehr Pfade, aber jeder Test sieht weniger Train. So entstehen die
          vielen überlappenden OOS-Pfade, aus denen die PBO geschätzt wird.
        </>
      }
    >
      <div className="mb-3 flex flex-wrap gap-6">
        <Slider label="k (Test-Gruppen)" value={k} min={1} max={3} step={1} onChange={setK} fmt={(v) => String(Math.round(v))} />
        <div className="flex items-end gap-3 text-xs text-zinc-400">
          {(["train", "test", "purge"] as Cell[]).map((c) => (
            <span key={c} className="flex items-center gap-1.5">
              <span className="h-3 w-3 rounded-sm" style={{ background: COLOR[c] }} />
              {c === "train" ? "Train" : c === "test" ? "Test" : "Purge/Embargo"}
            </span>
          ))}
        </div>
      </div>
      <div className="space-y-1">
        <div className="flex gap-1 pl-12 text-[10px] text-zinc-600">
          {Array.from({ length: N }, (_, i) => (
            <div key={i} className="flex-1 text-center">t{i}</div>
          ))}
        </div>
        {rows.map((cells, ri) => (
          <div key={ri} className="flex items-center gap-1">
            <div className="w-11 shrink-0 text-right font-mono text-[10px] text-zinc-600">#{ri + 1}</div>
            {cells.map((c, ci) => (
              <div
                key={ci}
                className="h-5 flex-1 rounded-sm"
                style={{ background: COLOR[c] }}
                title={c}
              />
            ))}
          </div>
        ))}
      </div>
    </VizFrame>
  );
}
