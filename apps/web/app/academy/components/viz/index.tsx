"use client";

import type { ComponentType } from "react";
import BlackScholesGreeks from "./BlackScholesGreeks";
import BrownianMotion from "./BrownianMotion";
import CovarianceEllipse from "./CovarianceEllipse";
import CostWall from "./CostWall";
import CPCVMatrix from "./CPCVMatrix";
import CrossSecRanking from "./CrossSecRanking";
import DrawdownPaths from "./DrawdownPaths";
import EventDrift from "./EventDrift";
import FootprintDelta from "./FootprintDelta";
import GradientDescent from "./GradientDescent";
import ICvsPnL from "./ICvsPnL";
import KellyCurve from "./KellyCurve";
import NormalDistribution from "./NormalDistribution";
import PermutationNull from "./PermutationNull";
import RandomWalk from "./RandomWalk";
import RegimeGate from "./RegimeGate";
import RegressionFit from "./RegressionFit";
import ReturnsHistogram from "./ReturnsHistogram";
import RollYieldCurve from "./RollYieldCurve";
import SharpeBlending from "./SharpeBlending";
import SharpeSampling from "./SharpeSampling";
import SpreadZScore from "./SpreadZScore";
import VolClustering from "./VolClustering";
import VolSmile from "./VolSmile";
import WalkForwardSplits from "./WalkForwardSplits";

/**
 * Registry of interactive visualisations keyed by the names used in
 * curriculum.json and in ``::viz Name`` directives inside module markdown.
 * Modules beyond M0 reference viz that are not built yet — those render a
 * labelled "coming soon" placeholder instead of crashing the page.
 */
export const VIZ: Record<string, ComponentType> = {
  NormalDistribution,
  RandomWalk,
  ReturnsHistogram,
  SharpeSampling,
  PermutationNull,
  CovarianceEllipse,
  RegressionFit,
  VolClustering,
  KellyCurve,
  GradientDescent,
  BlackScholesGreeks,
  BrownianMotion,
  CPCVMatrix,
  WalkForwardSplits,
  CrossSecRanking,
  RollYieldCurve,
  SpreadZScore,
  FootprintDelta,
  CostWall,
  DrawdownPaths,
  SharpeBlending,
  RegimeGate,
  EventDrift,
  VolSmile,
  ICvsPnL,
};

export function Viz({ name }: { name: string }) {
  const Component = VIZ[name];
  if (!Component) {
    return (
      <div className="rounded-lg border border-dashed border-zinc-700 bg-zinc-900/30 p-6 text-center text-sm text-zinc-500">
        Interaktive Visualisierung <span className="font-mono text-zinc-400">{name}</span> folgt
        in einem späteren Modul.
      </div>
    );
  }
  return <Component />;
}
