"use client";

import { useMemo, useState } from "react";
import type { OptSurface } from "@/lib/api";

/**
 * Dependency-free parameter-fitness surface for the Evolution Monitor.
 *
 * Renders the IS-fitness landscape over the two headline parameters either as a
 * rotatable 3-D mesh (isometric SVG projection, painter's-algorithm depth sort)
 * or as a top-down 2-D heatmap. The point the GA converged to is marked. A broad
 * bright plateau ⇒ a robust optimum; an isolated bright spike ⇒ a fragile,
 * curve-fit one — exactly the read this view exists for.
 */

// viridis-ish colour ramp: maps a normalized fitness t∈[0,1] to an rgb string.
const RAMP: [number, number, number][] = [
  [40, 25, 95], // deep indigo (worst)
  [38, 80, 150],
  [30, 145, 140],
  [90, 190, 90],
  [240, 220, 60], // yellow (best)
];
function colorFor(t: number): string {
  if (!Number.isFinite(t)) return "#2a2a32";
  const x = Math.min(Math.max(t, 0), 1) * (RAMP.length - 1);
  const i = Math.min(Math.floor(x), RAMP.length - 2);
  const f = x - i;
  const a = RAMP[i];
  const b = RAMP[i + 1];
  const r = Math.round(a[0] + (b[0] - a[0]) * f);
  const g = Math.round(a[1] + (b[1] - a[1]) * f);
  const bl = Math.round(a[2] + (b[2] - a[2]) * f);
  return `rgb(${r},${g},${bl})`;
}

const fmt = (x: number) => (Number.isInteger(x) ? String(x) : x.toFixed(3));

interface Props {
  surface: OptSurface;
}

export default function SurfacePlot({ surface }: Props) {
  const [mode, setMode] = useState<"3d" | "2d">("3d");
  const [yaw, setYaw] = useState(35); // degrees
  const [tilt, setTilt] = useState(0.55); // 0 = top-down, 1 = side-on

  const { x, y, z, best_x, best_y, x_name, y_name } = surface;

  // finite z range for normalization + colour
  const { zMin, zMax } = useMemo(() => {
    let lo = Infinity;
    let hi = -Infinity;
    for (const row of z)
      for (const v of row)
        if (v != null && Number.isFinite(v)) {
          lo = Math.min(lo, v);
          hi = Math.max(hi, v);
        }
    if (!Number.isFinite(lo)) {
      lo = 0;
      hi = 1;
    }
    return { zMin: lo, zMax: hi };
  }, [z]);
  const norm = (v: number | null) =>
    v == null || !Number.isFinite(v) || zMax === zMin ? 0 : (v - zMin) / (zMax - zMin);

  const W = 560;
  const H = 360;

  if (mode === "2d") {
    return (
      <Frame
        mode={mode}
        setMode={setMode}
        yaw={yaw}
        setYaw={setYaw}
        tilt={tilt}
        setTilt={setTilt}
        zMin={zMin}
        zMax={zMax}
        xName={x_name}
        yName={y_name}
      >
        <Heatmap x={x} y={y} z={z} norm={norm} bestX={best_x} bestY={best_y} W={W} H={H} />
      </Frame>
    );
  }

  // ── 3-D isometric projection ────────────────────────────────────────────
  const nx = x.length;
  const ny = y.length;
  const theta = (yaw * Math.PI) / 180;
  const cos = Math.cos(theta);
  const sin = Math.sin(theta);
  const zHeight = 150; // px of vertical lift for a full-range peak

  // world coords: gx,gy ∈ [-1,1], gz ∈ [0,1]
  const project = (i: number, j: number, zn: number) => {
    const gx = nx > 1 ? (i / (nx - 1)) * 2 - 1 : 0;
    const gy = ny > 1 ? (j / (ny - 1)) * 2 - 1 : 0;
    const ax = gx * cos - gy * sin;
    const ay = gx * sin + gy * cos;
    return { sx: ax, sy: ay * tilt - zn * (zHeight / 200), depth: ay };
  };

  // collect projected points to compute screen bounds
  const pts: { sx: number; sy: number }[] = [];
  for (let j = 0; j < ny; j++)
    for (let i = 0; i < nx; i++) pts.push(project(i, j, norm(z[j][i])));
  let minSx = Infinity,
    maxSx = -Infinity,
    minSy = Infinity,
    maxSy = -Infinity;
  for (const p of pts) {
    minSx = Math.min(minSx, p.sx);
    maxSx = Math.max(maxSx, p.sx);
    minSy = Math.min(minSy, p.sy);
    maxSy = Math.max(maxSy, p.sy);
  }
  const pad = 36;
  const scaleX = (W - 2 * pad) / (maxSx - minSx || 1);
  const scaleY = (H - 2 * pad) / (maxSy - minSy || 1);
  const scale = Math.min(scaleX, scaleY);
  const offX = pad + ((W - 2 * pad) - (maxSx - minSx) * scale) / 2;
  const offY = pad + ((H - 2 * pad) - (maxSy - minSy) * scale) / 2;
  const toScreen = (sx: number, sy: number) => ({
    X: offX + (sx - minSx) * scale,
    Y: offY + (sy - minSy) * scale,
  });

  // build cells (quads), back-to-front by depth
  type Cell = { d: number; pts: string; fill: string };
  const cells: Cell[] = [];
  for (let j = 0; j < ny - 1; j++) {
    for (let i = 0; i < nx - 1; i++) {
      const corners = [
        [i, j],
        [i + 1, j],
        [i + 1, j + 1],
        [i, j + 1],
      ];
      let d = 0;
      let zsum = 0;
      const poly: string[] = [];
      for (const [ci, cj] of corners) {
        const zn = norm(z[cj][ci]);
        const p = project(ci, cj, zn);
        const s = toScreen(p.sx, p.sy);
        poly.push(`${s.X.toFixed(1)},${s.Y.toFixed(1)}`);
        d += p.depth;
        zsum += zn;
      }
      cells.push({ d: d / 4, pts: poly.join(" "), fill: colorFor(zsum / 4) });
    }
  }
  cells.sort((a, b) => a.d - b.d); // far (small depth) first

  // best marker: nearest grid node to (best_x, best_y)
  let bi = 0;
  let bj = 0;
  if (best_x != null) bi = nearestIndex(x, best_x);
  if (best_y != null) bj = nearestIndex(y, best_y);
  const bzn = norm(z[bj]?.[bi] ?? null);
  const bTop = toScreen(...projTuple(project(bi, bj, bzn)));
  const bBase = toScreen(...projTuple(project(bi, bj, 0)));

  return (
    <Frame
      mode={mode}
      setMode={setMode}
      yaw={yaw}
      setYaw={setYaw}
      tilt={tilt}
      setTilt={setTilt}
      zMin={zMin}
      zMax={zMax}
      xName={x_name}
      yName={y_name}
    >
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full">
        {cells.map((c, k) => (
          <polygon key={k} points={c.pts} fill={c.fill} stroke="rgba(0,0,0,0.25)" strokeWidth={0.4} />
        ))}
        {/* best-individual marker with a drop line to its base */}
        <line x1={bBase.X} y1={bBase.Y} x2={bTop.X} y2={bTop.Y} stroke="#f43f5e" strokeWidth={1.4} strokeDasharray="3 2" />
        <circle cx={bTop.X} cy={bTop.Y} r={5} fill="#f43f5e" stroke="#fff" strokeWidth={1.4} />
        <text x={bTop.X + 8} y={bTop.Y - 6} fill="#fda4af" fontSize={10} className="font-mono">
          best · {x_name}={fmt(best_x ?? x[bi])}, {y_name}={fmt(best_y ?? y[bj])}
        </text>
      </svg>
    </Frame>
  );
}

function projTuple(p: { sx: number; sy: number }): [number, number] {
  return [p.sx, p.sy];
}

function nearestIndex(arr: number[], v: number): number {
  let best = 0;
  let bd = Infinity;
  for (let i = 0; i < arr.length; i++) {
    const d = Math.abs(arr[i] - v);
    if (d < bd) {
      bd = d;
      best = i;
    }
  }
  return best;
}

// ── 2-D heatmap (top-down view of the same surface) ─────────────────────────
function Heatmap({
  x,
  y,
  z,
  norm,
  bestX,
  bestY,
  W,
  H,
}: {
  x: number[];
  y: number[];
  z: (number | null)[][];
  norm: (v: number | null) => number;
  bestX: number | null;
  bestY: number | null;
  W: number;
  H: number;
}) {
  const pad = 40;
  const cw = (W - 2 * pad) / x.length;
  const ch = (H - 2 * pad) / y.length;
  const bi = bestX != null ? nearestIndex(x, bestX) : -1;
  const bj = bestY != null ? nearestIndex(y, bestY) : -1;
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full">
      {z.map((row, j) =>
        row.map((v, i) => (
          <rect
            key={`${i}-${j}`}
            x={pad + i * cw}
            y={pad + (y.length - 1 - j) * ch}
            width={cw + 0.5}
            height={ch + 0.5}
            fill={colorFor(norm(v))}
          />
        )),
      )}
      {bi >= 0 && bj >= 0 && (
        <circle
          cx={pad + (bi + 0.5) * cw}
          cy={pad + (y.length - 1 - bj + 0.5) * ch}
          r={5}
          fill="none"
          stroke="#f43f5e"
          strokeWidth={2}
        />
      )}
      {/* axis labels */}
      <text x={W / 2} y={H - 8} textAnchor="middle" fill="#71717a" fontSize={11}>
        {/* x label injected by Frame title */}
      </text>
    </svg>
  );
}

// ── shared chrome: mode toggle, rotation sliders, colour legend ─────────────
function Frame({
  children,
  mode,
  setMode,
  yaw,
  setYaw,
  tilt,
  setTilt,
  zMin,
  zMax,
  xName,
  yName,
}: {
  children: React.ReactNode;
  mode: "3d" | "2d";
  setMode: (m: "3d" | "2d") => void;
  yaw: number;
  setYaw: (n: number) => void;
  tilt: number;
  setTilt: (n: number) => void;
  zMin: number;
  zMax: number;
  xName: string;
  yName: string;
}) {
  return (
    <div>
      <div className="mb-2 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-1 rounded-md border border-zinc-800 p-0.5 text-xs">
          {(["3d", "2d"] as const).map((m) => (
            <button
              key={m}
              onClick={() => setMode(m)}
              className={`rounded px-2.5 py-1 ${mode === m ? "bg-zinc-700 text-zinc-100" : "text-zinc-400 hover:text-zinc-200"}`}
            >
              {m === "3d" ? "3-D Surface" : "2-D Heatmap"}
            </button>
          ))}
        </div>
        <div className="font-mono text-[11px] text-zinc-500">
          x: <span className="text-zinc-300">{xName}</span> · y:{" "}
          <span className="text-zinc-300">{yName}</span> · z: Fitness
        </div>
      </div>

      {children}

      {mode === "3d" && (
        <div className="mt-2 grid grid-cols-2 gap-4">
          <label className="text-xs text-zinc-400">
            Rotation {yaw}°
            <input
              type="range"
              min={0}
              max={360}
              value={yaw}
              onChange={(e) => setYaw(Number(e.target.value))}
              className="mt-1 w-full accent-emerald-500"
            />
          </label>
          <label className="text-xs text-zinc-400">
            Neigung {tilt.toFixed(2)}
            <input
              type="range"
              min={0.05}
              max={1}
              step={0.05}
              value={tilt}
              onChange={(e) => setTilt(Number(e.target.value))}
              className="mt-1 w-full accent-emerald-500"
            />
          </label>
        </div>
      )}

      {/* colour legend */}
      <div className="mt-3 flex items-center gap-2 text-[11px] text-zinc-500">
        <span>{zMin.toFixed(2)}</span>
        <div
          className="h-2 flex-1 rounded"
          style={{
            background: `linear-gradient(to right, ${colorFor(0)}, ${colorFor(0.25)}, ${colorFor(0.5)}, ${colorFor(0.75)}, ${colorFor(1)})`,
          }}
        />
        <span>{zMax.toFixed(2)}</span>
      </div>
    </div>
  );
}
