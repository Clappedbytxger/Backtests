// Order-flow delta strip: one signed bar per visible footprint cluster, aligned
// to the candle x-positions via timeScale().timeToCoordinate(). Cyan = net buy
// (ask) aggressor, magenta = net sell (bid) aggressor. Delta is tick-rule approx.

import type { ITimeScaleApi, Time } from "lightweight-charts";

import type { FootprintCluster } from "@/lib/api";

function clusterDelta(c: FootprintCluster): number {
  return c.levels.reduce((s, l) => s + l.delta, 0);
}

/** ctx must already be scaled to CSS pixels (caller applies devicePixelRatio). */
export function drawDeltaStrip(
  ctx: CanvasRenderingContext2D,
  timeScale: ITimeScaleApi<Time>,
  clusters: FootprintCluster[],
  width: number,
  height: number,
  up: string,
  down: string,
): void {
  if (!clusters.length) return;
  const maxAbs = Math.max(1, ...clusters.map((c) => Math.abs(clusterDelta(c))));
  const mid = height / 2;
  const barW = Math.max(1, Math.min(12, (width / clusters.length) * 0.6));

  ctx.strokeStyle = "rgba(255,255,255,0.08)";
  ctx.beginPath();
  ctx.moveTo(0, mid);
  ctx.lineTo(width, mid);
  ctx.stroke();

  for (const c of clusters) {
    const x = timeScale.timeToCoordinate(c.time as Time);
    if (x == null) continue;
    const d = clusterDelta(c);
    const h = (Math.abs(d) / maxAbs) * (mid - 2);
    ctx.fillStyle = d >= 0 ? up : down;
    if (d >= 0) ctx.fillRect(x - barW / 2, mid - h, barW, h);
    else ctx.fillRect(x - barW / 2, mid, barW, h);
  }
}
