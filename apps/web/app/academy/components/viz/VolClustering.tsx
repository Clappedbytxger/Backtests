"use client";

import { useMemo, useState } from "react";
import { CartesianGrid, ComposedChart, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { AXIS, GRID, gauss, rng, Slider, TOOLTIP, VizFrame } from "./controls";

const N = 300;

function autocorr1(x: number[]) {
  const m = x.reduce((a, b) => a + b, 0) / x.length;
  let num = 0, den = 0;
  for (let i = 1; i < x.length; i++) num += (x[i] - m) * (x[i - 1] - m);
  for (let i = 0; i < x.length; i++) den += (x[i] - m) ** 2;
  return num / den;
}

/**
 * Volatility clustering (a GARCH(1,1)-style process). Returns are nearly uncorrelated
 * (autocorr ≈ 0 — you can't predict direction), yet their MAGNITUDE clusters: big days
 * follow big days. The EWMA line tracks this. Persistence φ sets how "sticky" calm/storm
 * regimes are — the basis of vol-targeting (position ∝ target/realised vol).
 */
export default function VolClustering() {
  const [phi, setPhi] = useState(0.94);

  const { rows, acR, acAbs } = useMemo(() => {
    const r = rng(99);
    const omega = 1 - phi - 0.05;
    let sig2 = 1;
    const rets: number[] = [];
    const ewma: number[] = [];
    let e = 1;
    for (let i = 0; i < N; i++) {
      const ret = Math.sqrt(sig2) * gauss(r);
      rets.push(ret);
      e = 0.94 * e + 0.06 * ret * ret;
      ewma.push(Math.sqrt(e));
      sig2 = omega + 0.05 * ret * ret + phi * sig2; // GARCH(1,1) recursion
    }
    const rows = rets.map((ret, i) => ({ t: i, ret: +ret.toFixed(3), vol: +ewma[i].toFixed(3), negvol: +(-ewma[i]).toFixed(3) }));
    return { rows, acR: autocorr1(rets), acAbs: autocorr1(rets.map(Math.abs)) };
  }, [phi]);

  return (
    <VizFrame
      caption={
        <>
          Autokorrelation der Returns ≈ <b>{acR.toFixed(2)}</b> (Richtung kaum vorhersagbar), aber der
          <i> Beträge</i> = <b className="text-amber-400">{acAbs.toFixed(2)}</b> (Vol clustert!). Die gelbe
          EWMA-Hülle zeigt ruhige vs. stürmische Phasen. Höheres φ ⇒ längere Regime — und genau hier
          greift Vol-Targeting.
        </>
      }
    >
      <div className="mb-3 flex flex-wrap gap-6">
        <Slider label="Persistenz φ" value={phi} min={0.5} max={0.97} step={0.01} onChange={setPhi} fmt={(v) => v.toFixed(2)} />
      </div>
      <ResponsiveContainer width="100%" height={240}>
        <ComposedChart data={rows}>
          <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
          <XAxis dataKey="t" tick={AXIS} />
          <YAxis tick={AXIS} width={36} />
          <Tooltip contentStyle={TOOLTIP} />
          <Line dataKey="ret" stroke="#3b82f6" dot={false} strokeWidth={1} isAnimationActive={false} />
          <Line dataKey="vol" stroke="#eab308" dot={false} strokeWidth={1.5} isAnimationActive={false} />
          <Line dataKey="negvol" stroke="#eab308" dot={false} strokeWidth={1.5} isAnimationActive={false} />
        </ComposedChart>
      </ResponsiveContainer>
    </VizFrame>
  );
}
