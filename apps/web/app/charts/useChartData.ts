"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import {
  getCandles,
  getFootprint,
  getInstruments,
  type Candle,
  type ChartTime,
  type FootprintCluster,
  type Instrument,
} from "@/lib/api";

const PAGE_LIMIT = 500;

/** unix seconds for a candle/cluster time (number already, or "YYYY-MM-DD" -> sec). */
export function toSec(t: ChartTime): number {
  return typeof t === "number" ? t : Math.floor(Date.parse(`${t}T00:00:00Z`) / 1000);
}

function mergePrepend(older: Candle[], current: Candle[]): Candle[] {
  if (!current.length) return older;
  const firstSec = toSec(current[0].time);
  return [...older.filter((c) => toSec(c.time) < firstSec), ...current];
}

/**
 * All data + selection state for the charts terminal. Owns instrument discovery,
 * candle paging (prepend older bars on scroll-left) and the visible-range
 * footprint fetch. The chart component drives `loadMorePast` / `loadFootprint`.
 */
export function useChartData() {
  const [instruments, setInstruments] = useState<Instrument[]>([]);
  const [instrument, setInstrument] = useState<Instrument | null>(null);
  const [timeframe, setTimeframe] = useState("15m");
  const [rth, setRth] = useState(true);
  const [adjust, setAdjust] = useState(true); // split-adjust equities (TradingView parity)

  const [candles, setCandles] = useState<Candle[]>([]);
  const [footprint, setFootprint] = useState<FootprintCluster[]>([]);
  const [loading, setLoading] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const hasMorePast = useRef(true);
  const oldest = useRef<number | null>(null);
  const reqId = useRef(0); // guards against out-of-order responses

  useEffect(() => {
    getInstruments()
      .then((r) => {
        if (!r.ok) return setError(r.error ?? "instrument discovery failed");
        setInstruments(r.instruments);
        const pick =
          r.instruments.find((i) => i.ticker === "ES") ??
          r.instruments.find((i) => i.footprint) ??
          r.instruments[0] ??
          null;
        setInstrument(pick);
      })
      .catch((e) => setError(String(e)));
  }, []);

  // Reload candles whenever the instrument / timeframe / session filter changes.
  useEffect(() => {
    if (!instrument) return;
    const tf = instrument.available_tfs.includes(timeframe)
      ? timeframe
      : instrument.available_tfs[0];
    if (tf !== timeframe) {
      setTimeframe(tf);
      return;
    }
    const id = ++reqId.current;
    setLoading(true);
    setError(null);
    setFootprint([]);
    getCandles(instrument.ticker, tf, { limit: PAGE_LIMIT, rth, adjust })
      .then((r) => {
        if (id !== reqId.current) return;
        if (!r.ok) {
          setCandles([]);
          setError(r.error ?? "candles failed");
        } else {
          setCandles(r.candles);
          hasMorePast.current = r.has_more_past;
          oldest.current = r.candles.length ? toSec(r.candles[0].time) : null;
        }
      })
      .catch((e) => id === reqId.current && setError(String(e)))
      .finally(() => id === reqId.current && setLoading(false));
  }, [instrument, timeframe, rth, adjust]);

  const loadMorePast = useCallback(async () => {
    if (!instrument || !hasMorePast.current || loadingMore || oldest.current == null) return;
    setLoadingMore(true);
    const id = reqId.current;
    try {
      const r = await getCandles(instrument.ticker, timeframe, {
        end: oldest.current - 1,
        limit: PAGE_LIMIT,
        rth,
        adjust,
      });
      if (id !== reqId.current) return;
      if (r.ok && r.candles.length) {
        setCandles((prev) => mergePrepend(r.candles, prev));
        oldest.current = toSec(r.candles[0].time);
        hasMorePast.current = r.has_more_past;
      } else {
        hasMorePast.current = false;
      }
    } finally {
      if (id === reqId.current) setLoadingMore(false);
    }
  }, [instrument, timeframe, rth, adjust, loadingMore]);

  const loadFootprint = useCallback(
    async (from: number, to: number) => {
      if (!instrument?.footprint) {
        setFootprint([]);
        return;
      }
      try {
        const r = await getFootprint(instrument.ticker, timeframe, Math.floor(from), Math.ceil(to), {
          rth,
          adjust,
        });
        if (r.ok) setFootprint(r.clusters);
      } catch {
        /* transient — keep last footprint */
      }
    },
    [instrument, timeframe, rth, adjust],
  );

  const clearFootprint = useCallback(() => setFootprint([]), []);

  return {
    instruments,
    instrument,
    setInstrument,
    timeframe,
    setTimeframe,
    rth,
    setRth,
    adjust,
    setAdjust,
    candles,
    footprint,
    loading,
    loadingMore,
    error,
    loadMorePast,
    loadFootprint,
    clearFootprint,
  };
}
