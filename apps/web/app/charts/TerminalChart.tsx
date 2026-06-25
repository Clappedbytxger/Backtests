"use client";

import {
  CandlestickSeries,
  ColorType,
  createChart,
  CrosshairMode,
  HistogramSeries,
  type IChartApi,
  type ISeriesApi,
  type Time,
} from "lightweight-charts";
import { useEffect, useRef } from "react";

import type { Candle, FootprintCluster } from "@/lib/api";

import { drawDeltaStrip } from "./DeltaPanel";
import { drawFootprintCells } from "./Footprint";
import { aggregateLevels, drawVolumeProfile } from "./VolumeProfile";

const COLORS = {
  bg: "#0a0a0a",
  grid: "rgba(255,255,255,0.04)",
  text: "#8b8f98",
  axis: "rgba(255,255,255,0.08)",
  up: "#22d3ee", // cyan  — bullish / buy-aggressor
  down: "#f0457f", // magenta — bearish / sell-aggressor
  upVol: "rgba(34,211,238,0.40)",
  downVol: "rgba(240,69,127,0.40)",
  bid: "rgba(34,211,238,0.52)",
  ask: "rgba(240,69,127,0.52)",
  poc: "rgba(250,204,21,0.85)",
  va: "rgba(250,204,21,0.07)",
};

export interface VisibleRange {
  fromSec: number;
  toSec: number;
  bars: number;
}

interface Props {
  candles: Candle[];
  footprint: FootprintCluster[];
  showProfile: boolean;
  showDelta: boolean;
  footprintCells: boolean;
  fitKey: string; // changes on instrument/timeframe/rth switch -> re-zoom to recent bars
  onReachLeft: () => void;
  onVisibleRange: (r: VisibleRange) => void;
}

function drawHint(ctx: CanvasRenderingContext2D, w: number, text: string) {
  ctx.save();
  ctx.font = "11px ui-monospace, Menlo, monospace";
  ctx.fillStyle = "rgba(255,255,255,0.4)";
  ctx.textAlign = "center";
  ctx.fillText(text, w / 2, 18);
  ctx.restore();
}

function toSecTime(t: Time): number {
  if (typeof t === "number") return t;
  if (typeof t === "string") return Math.floor(Date.parse(`${t}T00:00:00Z`) / 1000);
  return Math.floor(Date.UTC(t.year, t.month - 1, t.day) / 1000);
}

function sizeCanvas(cv: HTMLCanvasElement, w: number, h: number, dpr: number) {
  cv.width = Math.max(1, Math.floor(w * dpr));
  cv.height = Math.max(1, Math.floor(h * dpr));
  cv.style.width = `${w}px`;
  cv.style.height = `${h}px`;
  const ctx = cv.getContext("2d");
  if (ctx) ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
}

export default function TerminalChart(props: Props) {
  const chartElRef = useRef<HTMLDivElement>(null);
  const profileRef = useRef<HTMLCanvasElement>(null);
  const deltaRef = useRef<HTMLCanvasElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candleRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const volRef = useRef<ISeriesApi<"Histogram"> | null>(null);
  const propsRef = useRef(props);
  propsRef.current = props;
  const debounce = useRef<number | undefined>(undefined);
  const lastFitKey = useRef<string>("");

  // Reads refs only, so the (once-bound) chart callbacks always see fresh state.
  const drawRef = useRef<() => void>(() => {});
  drawRef.current = () => {
    const chart = chartRef.current;
    const candle = candleRef.current;
    const el = chartElRef.current;
    if (!chart || !candle || !el) return;
    const w = el.clientWidth;
    const h = el.clientHeight;
    const dpr = window.devicePixelRatio || 1;
    const p = propsRef.current;

    const pc = profileRef.current;
    if (pc) {
      sizeCanvas(pc, w, h, dpr);
      const ctx = pc.getContext("2d");
      if (ctx) {
        ctx.clearRect(0, 0, w, h);
        let cellsDrawn = false;
        if (p.footprintCells && p.footprint.length) {
          cellsDrawn = drawFootprintCells(ctx, chart, candle, p.footprint, {
            bid: (a) => `rgba(34,211,238,${a})`,
            ask: (a) => `rgba(240,69,127,${a})`,
            bidText: "rgba(186,243,252,0.92)",
            askText: "rgba(252,206,232,0.92)",
            poc: COLORS.poc,
          });
          if (!cellsDrawn) drawHint(ctx, w, "zoom in for per-candle footprint");
        }
        if (!cellsDrawn && p.showProfile && p.footprint.length) {
          drawVolumeProfile(ctx, candle, aggregateLevels(p.footprint), w, h, {
            bid: COLORS.bid,
            ask: COLORS.ask,
            poc: COLORS.poc,
            va: COLORS.va,
          });
        }
      }
    }

    const dc = deltaRef.current;
    if (dc && p.showDelta) {
      const dh = dc.clientHeight || 64;
      sizeCanvas(dc, w, dh, dpr);
      const ctx = dc.getContext("2d");
      if (ctx) {
        ctx.clearRect(0, 0, w, dh);
        if (p.footprint.length) {
          drawDeltaStrip(ctx, chart.timeScale(), p.footprint, w, dh, COLORS.up, COLORS.down);
        }
      }
    }
  };

  // Create the chart once.
  useEffect(() => {
    const el = chartElRef.current;
    if (!el) return;
    const chart = createChart(el, {
      autoSize: true,
      layout: {
        background: { type: ColorType.Solid, color: COLORS.bg },
        textColor: COLORS.text,
        fontSize: 11,
        fontFamily: "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace",
        attributionLogo: false,
      },
      grid: { vertLines: { color: COLORS.grid }, horzLines: { color: COLORS.grid } },
      crosshair: { mode: CrosshairMode.Normal },
      rightPriceScale: { borderColor: COLORS.axis, scaleMargins: { top: 0.08, bottom: 0.02 } },
      timeScale: {
        borderColor: COLORS.axis,
        timeVisible: true,
        secondsVisible: false,
        rightOffset: 6,
      },
    });
    const candle = chart.addSeries(CandlestickSeries, {
      upColor: COLORS.up,
      downColor: COLORS.down,
      wickUpColor: COLORS.up,
      wickDownColor: COLORS.down,
      borderVisible: false,
      priceLineVisible: false,
    });
    const vol = chart.addSeries(HistogramSeries, {
      priceFormat: { type: "volume" },
      priceScaleId: "vol",
      priceLineVisible: false,
      lastValueVisible: false,
    });
    chart.priceScale("vol").applyOptions({ scaleMargins: { top: 0.85, bottom: 0 } });
    chartRef.current = chart;
    candleRef.current = candle;
    volRef.current = vol;

    const ts = chart.timeScale();
    ts.subscribeVisibleLogicalRangeChange((lr) => {
      drawRef.current();
      if (!lr) return;
      if (lr.from < 8) propsRef.current.onReachLeft();
      window.clearTimeout(debounce.current);
      debounce.current = window.setTimeout(() => {
        const tr = ts.getVisibleRange();
        if (!tr) return;
        propsRef.current.onVisibleRange({
          fromSec: toSecTime(tr.from),
          toSec: toSecTime(tr.to),
          bars: Math.round(lr.to - lr.from),
        });
      }, 220);
    });
    chart.subscribeCrosshairMove(() => drawRef.current());

    const ro = new ResizeObserver(() => requestAnimationFrame(() => drawRef.current()));
    ro.observe(el);
    return () => {
      ro.disconnect();
      window.clearTimeout(debounce.current);
      chart.remove();
      chartRef.current = null;
      candleRef.current = null;
      volRef.current = null;
    };
  }, []);

  // Push candle + volume data.
  useEffect(() => {
    const candle = candleRef.current;
    const vol = volRef.current;
    const chart = chartRef.current;
    if (!candle || !vol || !chart) return;
    candle.setData(
      props.candles.map((c) => ({
        time: c.time as Time,
        open: c.open,
        high: c.high,
        low: c.low,
        close: c.close,
      })),
    );
    vol.setData(
      props.candles.map((c) => ({
        time: c.time as Time,
        value: c.volume,
        color: c.close >= c.open ? COLORS.upVol : COLORS.downVol,
      })),
    );
    // On a fresh instrument/timeframe (not a history prepend) zoom to recent bars.
    const n = props.candles.length;
    if (props.fitKey !== lastFitKey.current && n > 0) {
      lastFitKey.current = props.fitKey;
      chart.timeScale().setVisibleLogicalRange({ from: Math.max(0, n - 120), to: n + 6 });
    }
    requestAnimationFrame(() => drawRef.current());
  }, [props.candles, props.fitKey]);

  // Redraw overlays on footprint / toggle changes.
  useEffect(() => {
    requestAnimationFrame(() => drawRef.current());
  }, [props.footprint, props.showProfile, props.showDelta, props.footprintCells]);

  return (
    <div className="flex h-full w-full flex-col">
      <div className="relative min-h-0 flex-1">
        <div ref={chartElRef} className="h-full w-full" />
        {/* z-10: lightweight-charts paints its own canvases at z-index 1/2 */}
        <canvas ref={profileRef} className="pointer-events-none absolute inset-0 z-10" />
      </div>
      {props.showDelta && (
        <div className="relative h-16 border-t border-white/5">
          <canvas ref={deltaRef} className="absolute inset-0 h-full w-full" />
          <span className="absolute left-2 top-1 font-mono text-[10px] uppercase tracking-wider text-zinc-500">
            Δ cumulative delta · approx
          </span>
        </div>
      )}
    </div>
  );
}
