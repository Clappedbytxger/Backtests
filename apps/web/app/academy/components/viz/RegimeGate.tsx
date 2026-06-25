"use client";

import { useMemo, useState } from "react";
import { Area, ComposedChart, CartesianGrid, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { AXIS, GRID, gauss, rng, Slider, TOOLTIP, VizFrame } from "./controls";

const T = 300;

function sharpe(rets: number[]) {
  const a = rets.filter((x) => x !== 0);
  if (a.length < 5) return 0;
  const m = a.reduce((s, b) => s + b, 0) / a.length;
  const v = Math.max(a.reduce((s, b) => s + (b - m) ** 2, 0) / a.length, 1e-9);
  return (m / Math.sqrt(v)) * Math.sqrt(252);
}

/**
 * Regime gating as an overlay. A hidden macro state alternates bull/bear; an observable
 * indicator (a slow, noisy momentum) tracks it imperfectly. The gate holds the asset only
 * while the indicator is above a threshold, else flat. A good gate sidesteps the bear regimes
 * — but the gate is NOT itself an edge, and with few regime episodes it is fragile (0086).
 */
export default function RegimeGate() {
  const [threshold, setThreshold] = useState(0);

  const { data, gatedSharpe, bhSharpe, exposure } = useMemo(() => {
    const r = rng(44);
    // hidden regime: slowly switching drift
    let drift = 0.0006;
    const rets: number[] = [];
    const indicator: number[] = [];
    let ind = 0;
    for (let t = 0; t < T; t++) {
      if (r() < 0.012) drift = -drift; // occasional regime flip
      const ret = drift + 0.01 * gauss(r);
      rets.push(ret);
      ind = 0.95 * ind + 0.05 * (ret / 0.01); // slow noisy momentum proxy
      indicator.push(ind);
    }
    let be = 1, ge = 1;
    const gatedRets: number[] = [];
    const rows = [{ t: 0, bh: 100, gated: 100, on: 0 }];
    for (let t = 1; t < T; t++) {
      const on = indicator[t - 1] > threshold ? 1 : 0; // decide on yesterday's indicator
      be *= 1 + rets[t];
      ge *= 1 + on * rets[t];
      gatedRets.push(on * rets[t]);
      rows.push({ t, bh: +(be * 100).toFixed(2), gated: +(ge * 100).toFixed(2), on });
    }
    const exposure = (100 * rows.filter((x) => x.on).length) / rows.length;
    // shade band for "in market": draw gated value when on, else null
    const data = rows.map((x) => ({ ...x, hold: x.on ? x.gated : null }));
    return { data, gatedSharpe: sharpe(gatedRets), bhSharpe: sharpe(rets), exposure };
  }, [threshold]);

  return (
    <VizFrame
      caption={
        <>
          Grün = Strategie mit Regime-Gate, grau = Buy &amp; Hold. Das Gate hält nur, wenn der Indikator über
          der Schwelle liegt (Exposure {exposure.toFixed(0)} %). Gated-Sharpe{" "}
          <b className="text-emerald-400">{gatedSharpe.toFixed(2)}</b> vs. B&amp;H{" "}
          <b>{bhSharpe.toFixed(2)}</b>. Das Gate umgeht die Bär-Regimes — ist aber selbst kein Edge und bei
          wenigen Regime-Episoden fragil (0086).
        </>
      }
    >
      <div className="mb-3 flex flex-wrap gap-6">
        <Slider label="Gate-Schwelle" value={threshold} min={-1} max={1} step={0.05} onChange={setThreshold} fmt={(v) => v.toFixed(2)} />
      </div>
      <ResponsiveContainer width="100%" height={240}>
        <ComposedChart data={data}>
          <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
          <XAxis dataKey="t" tick={AXIS} />
          <YAxis tick={AXIS} width={42} domain={["auto", "auto"]} />
          <Tooltip contentStyle={TOOLTIP} />
          <Line dataKey="bh" stroke="#71717a" dot={false} strokeWidth={1.5} isAnimationActive={false} name="Buy & Hold" />
          <Line dataKey="gated" stroke="#22c55e" dot={false} strokeWidth={2} isAnimationActive={false} name="Gated" />
          <Area dataKey="hold" stroke="none" fill="#22c55e" fillOpacity={0.08} isAnimationActive={false} />
        </ComposedChart>
      </ResponsiveContainer>
    </VizFrame>
  );
}
