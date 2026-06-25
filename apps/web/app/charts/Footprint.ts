// Stage 2 — per-candle footprint cells. For each visible cluster, draw the
// bid×ask volume per price level beside the candle (bid left/cyan, ask
// right/magenta), POC row outlined. Only legible when zoomed in, so the caller
// falls back to the VPVR (Stage 1) when bar spacing is too small.

import type { IChartApi, ISeriesApi, SeriesType, Time } from "lightweight-charts";

import type { FootprintCluster } from "@/lib/api";

export interface CellTheme {
  bid: (a: number) => string;
  ask: (a: number) => string;
  bidText: string;
  askText: string;
  poc: string;
}

/** Pixel distance between adjacent clusters (0 if not measurable). */
export function footprintBarSpacing(chart: IChartApi, clusters: FootprintCluster[]): number {
  if (clusters.length < 2) return 0;
  const ts = chart.timeScale();
  const xs: number[] = [];
  for (const c of clusters) {
    const x = ts.timeToCoordinate(c.time as Time);
    if (x != null) xs.push(x);
    if (xs.length >= 2) break;
  }
  return xs.length >= 2 ? Math.abs(xs[1] - xs[0]) : 0;
}

function fmt(v: number): string {
  if (v >= 100000) return `${Math.round(v / 1000)}k`;
  if (v >= 1000) return `${(v / 1000).toFixed(1)}k`;
  return `${Math.round(v)}`;
}

const MIN_SPACING = 36; // px per cluster needed before cells are readable

/** Returns false (without drawing) when too zoomed-out for legible cells. */
export function drawFootprintCells(
  ctx: CanvasRenderingContext2D,
  chart: IChartApi,
  series: ISeriesApi<SeriesType>,
  clusters: FootprintCluster[],
  theme: CellTheme,
): boolean {
  if (!clusters.length) return false;
  const spacing = footprintBarSpacing(chart, clusters);
  if (spacing < MIN_SPACING) return false;

  const ts = chart.timeScale();
  const cellW = Math.min(spacing * 0.92, 140);
  const half = cellW / 2;
  ctx.font = "10px ui-monospace, Menlo, Consolas, monospace";
  ctx.textBaseline = "middle";

  for (const c of clusters) {
    const xc = ts.timeToCoordinate(c.time as Time);
    if (xc == null) continue;

    const ys = c.levels.map((l) => series.priceToCoordinate(l.price));
    let rowH = 12;
    for (let i = 1; i < ys.length; i++) {
      const a = ys[i - 1];
      const b = ys[i];
      if (a != null && b != null) {
        rowH = Math.max(2, Math.abs(b - a));
        break;
      }
    }
    const showText = rowH >= 9 && cellW >= 46;

    for (let i = 0; i < c.levels.length; i++) {
      const y = ys[i];
      if (y == null) continue;
      const l = c.levels[i];
      const top = y - rowH / 2;
      const denom = l.total || 1;
      ctx.fillStyle = theme.bid(0.1 + (l.bid_volume / denom) * 0.4);
      ctx.fillRect(xc - half, top, half, rowH - 1);
      ctx.fillStyle = theme.ask(0.1 + (l.ask_volume / denom) * 0.4);
      ctx.fillRect(xc, top, half, rowH - 1);

      if (l.price === c.poc_price) {
        ctx.strokeStyle = theme.poc;
        ctx.lineWidth = 1;
        ctx.strokeRect(xc - half, top, cellW, rowH - 1);
      }
      if (showText) {
        ctx.fillStyle = theme.bidText;
        ctx.textAlign = "left";
        ctx.fillText(fmt(l.bid_volume), xc - half + 3, y);
        ctx.fillStyle = theme.askText;
        ctx.textAlign = "right";
        ctx.fillText(fmt(l.ask_volume), xc + half - 3, y);
      }
    }
  }
  ctx.textAlign = "left";
  return true;
}
