// Volume-by-price (VPVR) overlay: aggregate the visible footprint clusters into
// one price->volume profile and paint it on a canvas synced to the chart's price
// scale via series.priceToCoordinate(). Bid (cyan) / ask (magenta) split + POC.

import type { ISeriesApi, SeriesType } from "lightweight-charts";

import type { FootprintCluster } from "@/lib/api";

export interface AggLevel {
  price: number;
  bid: number;
  ask: number;
  total: number;
}

export interface ProfileAgg {
  levels: AggLevel[]; // sorted by price descending (high -> low)
  poc: number | null;
  vah: number | null; // value-area high price
  val: number | null; // value-area low price
  maxTotal: number;
}

/** Sum bid/ask/total per price across clusters (all share one bin grid per request). */
export function aggregateLevels(clusters: FootprintCluster[]): ProfileAgg {
  const map = new Map<number, AggLevel>();
  for (const c of clusters) {
    for (const lv of c.levels) {
      const e = map.get(lv.price) ?? { price: lv.price, bid: 0, ask: 0, total: 0 };
      e.bid += lv.bid_volume;
      e.ask += lv.ask_volume;
      e.total += lv.total;
      map.set(lv.price, e);
    }
  }
  const levels = [...map.values()].sort((a, b) => b.price - a.price);
  if (!levels.length) return { levels, poc: null, vah: null, val: null, maxTotal: 0 };

  const maxTotal = Math.max(...levels.map((l) => l.total));
  const grand = levels.reduce((s, l) => s + l.total, 0);
  let pocI = 0;
  for (let i = 1; i < levels.length; i++) if (levels[i].total > levels[pocI].total) pocI = i;

  // expand a 70% value area outward from the POC, always taking the larger neighbour
  let loI = pocI;
  let hiI = pocI;
  let acc = levels[pocI].total;
  const target = grand * 0.7;
  while (acc < target && (loI > 0 || hiI < levels.length - 1)) {
    const above = loI > 0 ? levels[loI - 1].total : -1; // higher price
    const below = hiI < levels.length - 1 ? levels[hiI + 1].total : -1; // lower price
    if (above >= below) acc += levels[--loI].total;
    else acc += levels[++hiI].total;
  }
  return { levels, poc: levels[pocI].price, vah: levels[loI].price, val: levels[hiI].price, maxTotal };
}

export interface ProfileTheme {
  bid: string;
  ask: string;
  poc: string;
  va: string;
}

/** ctx must already be scaled to CSS pixels (caller applies devicePixelRatio). */
export function drawVolumeProfile(
  ctx: CanvasRenderingContext2D,
  series: ISeriesApi<SeriesType>,
  agg: ProfileAgg,
  width: number,
  height: number,
  theme: ProfileTheme,
): void {
  if (!agg.levels.length || agg.maxTotal <= 0) return;
  const profileW = Math.min(280, width * 0.34);
  const x0 = width - 64; // right anchor, left of the price axis

  // value-area band
  if (agg.vah != null && agg.val != null) {
    const yTop = series.priceToCoordinate(agg.vah);
    const yBot = series.priceToCoordinate(agg.val);
    if (yTop != null && yBot != null) {
      ctx.fillStyle = theme.va;
      ctx.fillRect(x0 - profileW, Math.min(yTop, yBot), profileW, Math.abs(yBot - yTop) || 1);
    }
  }

  // row height from the first measurable adjacent gap
  const ys = agg.levels.map((l) => series.priceToCoordinate(l.price));
  let rowH = 3;
  for (let i = 1; i < ys.length; i++) {
    const a = ys[i - 1];
    const b = ys[i];
    if (a != null && b != null) {
      rowH = Math.max(1, Math.abs(b - a) - 1);
      break;
    }
  }

  for (let i = 0; i < agg.levels.length; i++) {
    const y = ys[i];
    if (y == null) continue;
    const l = agg.levels[i];
    const w = (l.total / agg.maxTotal) * profileW;
    const bidW = l.total > 0 ? w * (l.bid / l.total) : 0;
    ctx.fillStyle = theme.ask; // ask extends to the left (outer)
    ctx.fillRect(x0 - w, y - rowH / 2, w - bidW, rowH);
    ctx.fillStyle = theme.bid; // bid nearest the right anchor (inner)
    ctx.fillRect(x0 - bidW, y - rowH / 2, bidW, rowH);
  }

  // POC line across the whole pane
  if (agg.poc != null) {
    const y = series.priceToCoordinate(agg.poc);
    if (y != null) {
      ctx.strokeStyle = theme.poc;
      ctx.lineWidth = 1;
      ctx.setLineDash([3, 3]);
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(width, y);
      ctx.stroke();
      ctx.setLineDash([]);
    }
  }
}
