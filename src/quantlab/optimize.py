"""Genetic-algorithm parameter optimizer with built-in overfitting protection.

Replaces brute-force grid search for tuning strategy parameters. The core is a
classic real-valued GA (tournament / roulette selection, uniform crossover,
*adaptive* mutation) that maximizes a configurable fitness function — by default
``Sharpe * (1 - |MaxDrawdown|)`` — but it is wrapped in a mandatory
In-Sample / Out-of-Sample protocol:

    * fitness is computed ONLY on the in-sample slice,
    * the final population is re-scored on the untouched out-of-sample slice,
    * the IS→OOS *haircut* (drop in fitness, in %) flags overfit parameter sets
      (> ``haircut_reject_pct`` ⇒ marked unstable).

Look-ahead safety is inherited from :func:`quantlab.backtest.run_backtest`, which
shifts every signal by one bar; the optimizer never sees future data because the
IS and OOS slices are split chronologically.

The optimizer is strategy-agnostic: a *strategy* is any callable
``(prices, **params) -> pd.Series`` returning a target-position signal. A ready
``ma_crossover_strategy`` is included for the demo/tests.

The driver :func:`run_ga` is a generator-friendly wrapper: pass ``on_generation``
to stream per-generation telemetry (best/avg/worst fitness, diversity, mutation
rate) for a live convergence monitor.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .backtest import run_backtest
from .costs import CostModel
from .metrics import compute_metrics

# A strategy maps (prices, **params) to a target-position signal (decision-time).
StrategyFn = Callable[..., pd.Series]
# A fitness function maps a metrics dict to a single scalar to MAXIMIZE.
FitnessFn = Callable[[dict], float]


# ────────────────────────────────────────────────────────────────────────────
# Parameter space (the chromosome encoding)
# ────────────────────────────────────────────────────────────────────────────
@dataclass
class ParamSpec:
    """One tunable parameter — a single gene of the chromosome.

    Attributes:
        name: keyword passed to the strategy function.
        low / high: inclusive bounds of the search range.
        integer: round the decoded value to the nearest int (e.g. an SMA window).
        step: optional quantization step (e.g. ``0.5`` for a stop in %); applied
            after clipping. ``None`` keeps the value continuous.
    """

    name: str
    low: float
    high: float
    integer: bool = False
    step: float | None = None

    def clip(self, value: float) -> float:
        """Clamp ``value`` into the range and apply integer/step quantization."""
        v = float(np.clip(value, self.low, self.high))
        if self.step:
            v = self.low + round((v - self.low) / self.step) * self.step
            v = float(np.clip(v, self.low, self.high))
        if self.integer:
            v = float(int(round(v)))
        return v


@dataclass
class ParamSpace:
    """The full chromosome layout: an ordered list of :class:`ParamSpec`."""

    specs: list[ParamSpec]

    def __post_init__(self) -> None:
        if not self.specs:
            raise ValueError("ParamSpace needs at least one ParamSpec")

    @property
    def dim(self) -> int:
        return len(self.specs)

    @property
    def names(self) -> list[str]:
        return [s.name for s in self.specs]

    @property
    def lows(self) -> np.ndarray:
        return np.array([s.low for s in self.specs], dtype=float)

    @property
    def highs(self) -> np.ndarray:
        return np.array([s.high for s in self.specs], dtype=float)

    def clip_vector(self, vec: np.ndarray) -> np.ndarray:
        """Clip + quantize a whole chromosome gene-by-gene."""
        return np.array([s.clip(v) for s, v in zip(self.specs, vec)], dtype=float)

    def decode(self, vec: np.ndarray) -> dict[str, float]:
        """Turn a (clipped) chromosome into a ``{name: value}`` params dict."""
        clipped = self.clip_vector(vec)
        return {s.name: v for s, v in zip(self.specs, clipped)}

    def random_population(self, n: int, rng: np.random.Generator) -> np.ndarray:
        """Uniformly sample ``n`` chromosomes inside the bounds (then quantize)."""
        raw = rng.uniform(self.lows, self.highs, size=(n, self.dim))
        return np.array([self.clip_vector(row) for row in raw])


# ────────────────────────────────────────────────────────────────────────────
# Fitness functions
# ────────────────────────────────────────────────────────────────────────────
def fitness_sharpe_dd(metrics: dict) -> float:
    """Default fitness: ``Sharpe * (1 - |MaxDrawdown|)``.

    Rewards risk-adjusted return while penalizing deep drawdowns: a Sharpe of 1.5
    at a 40% drawdown scores 1.5·0.6 = 0.9, below the same Sharpe at a 10% drawdown
    (1.5·0.9 = 1.35). Non-finite inputs collapse to a large negative number so the
    GA discards them.
    """
    sharpe = metrics.get("sharpe", float("nan"))
    mdd = metrics.get("max_drawdown", float("nan"))
    if not (math.isfinite(sharpe) and math.isfinite(mdd)):
        return -1e9
    return float(sharpe * (1.0 - abs(mdd)))


def fitness_sharpe(metrics: dict) -> float:
    """Plain annualized Sharpe ratio."""
    s = metrics.get("sharpe", float("nan"))
    return float(s) if math.isfinite(s) else -1e9


def fitness_calmar(metrics: dict) -> float:
    """Calmar ratio (CAGR / |MaxDD|)."""
    c = metrics.get("calmar", float("nan"))
    return float(c) if math.isfinite(c) else -1e9


FITNESS_FUNCTIONS: dict[str, FitnessFn] = {
    "sharpe_dd": fitness_sharpe_dd,
    "sharpe": fitness_sharpe,
    "calmar": fitness_calmar,
}


# ────────────────────────────────────────────────────────────────────────────
# Built-in demo strategy (moving-average crossover)
# ────────────────────────────────────────────────────────────────────────────
def ma_crossover_strategy(
    prices: pd.DataFrame,
    sma_fast: float = 20,
    sma_slow: float = 100,
    stop_loss_pct: float = 0.0,
) -> pd.Series:
    """Long-only SMA crossover, decision-time signal (no look-ahead).

    Long (1.0) when the fast SMA is above the slow SMA, flat otherwise. An optional
    intrabar trailing ``stop_loss_pct`` (fraction, e.g. ``0.05`` = 5%) flattens the
    position once the close falls that far below the in-position running peak. All
    series are evaluated at the close of ``t``; :func:`run_backtest` shifts by one
    bar, so the position is only held from ``t+1``.
    """
    fast = int(round(sma_fast))
    slow = int(round(sma_slow))
    if fast >= slow:  # degenerate genome — no edge to test
        return pd.Series(0.0, index=prices.index)

    close = prices["Close"].astype(float)
    sma_f = close.rolling(fast).mean()
    sma_s = close.rolling(slow).mean()
    raw = (sma_f > sma_s).astype(float)

    if stop_loss_pct and stop_loss_pct > 0:
        raw = _apply_trailing_stop(close, raw, stop_loss_pct)

    return raw.fillna(0.0)


def _apply_trailing_stop(close: pd.Series, signal: pd.Series, stop_pct: float) -> pd.Series:
    """Flatten the signal once price drops ``stop_pct`` below the in-trade peak.

    Operates only on close-of-bar info (peak so far), so it stays decision-time
    safe. A re-entry is allowed once the base signal turns on again in a new run.
    """
    vals = signal.to_numpy(copy=True)
    px = close.to_numpy()
    peak = np.nan
    stopped = False
    for i in range(len(vals)):
        if vals[i] <= 0:
            peak, stopped = np.nan, False
            continue
        if stopped:  # stay out until the base signal resets (handled by <=0 above)
            vals[i] = 0.0
            continue
        peak = px[i] if np.isnan(peak) else max(peak, px[i])
        if peak > 0 and px[i] <= peak * (1.0 - stop_pct):
            vals[i] = 0.0
            stopped = True
    return pd.Series(vals, index=signal.index)


# ────────────────────────────────────────────────────────────────────────────
# Evaluator: chromosome → fitness on a price slice
# ────────────────────────────────────────────────────────────────────────────
class Evaluator:
    """Scores chromosomes by backtesting a strategy on a price slice.

    Memoizes by the (rounded) parameter tuple so the GA never re-runs an identical
    backtest — genomes recur heavily once the population converges.
    """

    def __init__(
        self,
        prices: pd.DataFrame,
        space: ParamSpace,
        strategy: StrategyFn,
        fitness: FitnessFn,
        cost_model: CostModel | None = None,
    ) -> None:
        self.prices = prices
        self.space = space
        self.strategy = strategy
        self.fitness = fitness
        self.cost_model = cost_model
        self._cache: dict[tuple, dict] = {}

    def _key(self, params: dict[str, float]) -> tuple:
        return tuple(round(params[n], 6) for n in self.space.names)

    def evaluate(self, vec: np.ndarray) -> tuple[float, dict]:
        """Return ``(fitness, metrics)`` for one chromosome (cached)."""
        params = self.space.decode(vec)
        key = self._key(params)
        hit = self._cache.get(key)
        if hit is not None:
            return hit["fitness"], hit["metrics"]
        metrics = self._run(params)
        fit = self.fitness(metrics)
        self._cache[key] = {"fitness": fit, "metrics": metrics}
        return fit, metrics

    def _run(self, params: dict[str, float]) -> dict:
        try:
            signal = self.strategy(self.prices, **params)
            bt = run_backtest(self.prices, signal, cost_model=self.cost_model)
            m = compute_metrics(bt["returns"])
            m["n_trades"] = int(len(bt["trades"]))
            return m
        except Exception:  # noqa: BLE001 - a broken genome scores worst, never crashes the run
            return {"sharpe": float("nan"), "max_drawdown": float("nan"),
                    "cagr": float("nan"), "calmar": float("nan"), "n_trades": 0}


# ────────────────────────────────────────────────────────────────────────────
# GA operators
# ────────────────────────────────────────────────────────────────────────────
def tournament_select(
    pop: np.ndarray, fitness: np.ndarray, rng: np.random.Generator, k: int = 3
) -> np.ndarray:
    """Pick one parent as the fittest of ``k`` random contenders."""
    idx = rng.integers(0, len(pop), size=k)
    best = idx[np.argmax(fitness[idx])]
    return pop[best].copy()


def roulette_select(
    pop: np.ndarray, fitness: np.ndarray, rng: np.random.Generator
) -> np.ndarray:
    """Fitness-proportionate selection (rank-shifted so negatives are valid)."""
    shifted = fitness - fitness.min() + 1e-9
    total = shifted.sum()
    probs = shifted / total if total > 0 else np.full(len(pop), 1.0 / len(pop))
    return pop[rng.choice(len(pop), p=probs)].copy()


def uniform_crossover(
    a: np.ndarray, b: np.ndarray, rng: np.random.Generator, swap_prob: float = 0.5
) -> tuple[np.ndarray, np.ndarray]:
    """Per-gene uniform crossover: each gene independently swapped with ``swap_prob``."""
    mask = rng.random(len(a)) < swap_prob
    c1, c2 = a.copy(), b.copy()
    c1[mask], c2[mask] = b[mask], a[mask]
    return c1, c2


def gaussian_mutate(
    vec: np.ndarray, space: ParamSpace, rate: float, scale: float, rng: np.random.Generator
) -> np.ndarray:
    """Add Gaussian noise to genes selected with probability ``rate``.

    The noise std per gene is ``scale * (high - low)`` so each dimension mutates on
    its own scale. The result is clipped/quantized back into the space.
    """
    span = space.highs - space.lows
    mask = rng.random(space.dim) < rate
    noise = rng.normal(0.0, scale * span) * mask
    return space.clip_vector(vec + noise)


def population_diversity(pop: np.ndarray, space: ParamSpace) -> float:
    """Mean per-gene std, normalized by each gene's range (0 = fully converged)."""
    span = space.highs - space.lows
    span = np.where(span == 0, 1.0, span)
    return float(np.mean(pop.std(axis=0) / span))


# ────────────────────────────────────────────────────────────────────────────
# GA config + per-generation telemetry
# ────────────────────────────────────────────────────────────────────────────
@dataclass
class GAConfig:
    """Hyper-parameters of the evolutionary loop."""

    population_size: int = 40
    generations: int = 30
    selection: str = "tournament"  # "tournament" | "roulette"
    tournament_k: int = 3
    crossover_prob: float = 0.9
    elitism: int = 2
    # Adaptive mutation: rate scales with remaining diversity, so it FALLS as the
    # population converges. ``base_mutation_rate`` is the early (high-diversity)
    # rate, ``min_mutation_rate`` the converged floor.
    base_mutation_rate: float = 0.3
    min_mutation_rate: float = 0.05
    mutation_scale: float = 0.15  # gene noise std as a fraction of each gene range
    seed: int = 42

    def __post_init__(self) -> None:
        if self.selection not in ("tournament", "roulette"):
            raise ValueError(f"unknown selection '{self.selection}'")
        if self.elitism >= self.population_size:
            raise ValueError("elitism must be smaller than population_size")


@dataclass
class GenerationStats:
    """One generation's telemetry for the live convergence monitor."""

    generation: int
    best_fitness: float
    avg_fitness: float
    worst_fitness: float
    diversity: float
    mutation_rate: float
    best_params: dict[str, float]

    def to_dict(self) -> dict:
        return {
            "generation": self.generation,
            "best_fitness": _finite(self.best_fitness),
            "avg_fitness": _finite(self.avg_fitness),
            "worst_fitness": _finite(self.worst_fitness),
            "diversity": _finite(self.diversity),
            "mutation_rate": _finite(self.mutation_rate),
            "best_params": self.best_params,
        }


def _finite(x: float) -> float | None:
    return float(x) if isinstance(x, (int, float)) and math.isfinite(x) else None


# ────────────────────────────────────────────────────────────────────────────
# The evolutionary loop
# ────────────────────────────────────────────────────────────────────────────
def evolve(
    evaluator: Evaluator, space: ParamSpace, config: GAConfig
) -> Iterable[tuple[GenerationStats, np.ndarray, np.ndarray]]:
    """Run the GA, yielding ``(stats, population, fitness)`` after each generation.

    Yielding lets a caller stream progress (the live monitor) without re-running.
    The final yield holds the converged population, sorted best-first by IS fitness.
    """
    rng = np.random.default_rng(config.seed)
    pop = space.random_population(config.population_size, rng)
    fitness = np.array([evaluator.evaluate(ind)[0] for ind in pop])

    init_diversity = max(population_diversity(pop, space), 1e-9)
    select = (lambda p, f: tournament_select(p, f, rng, config.tournament_k)) \
        if config.selection == "tournament" else (lambda p, f: roulette_select(p, f, rng))

    for gen in range(config.generations):
        diversity = population_diversity(pop, space)
        # Adaptive mutation: high while diverse, decaying to the floor at convergence.
        div_ratio = min(diversity / init_diversity, 1.0)
        mut_rate = config.min_mutation_rate + \
            (config.base_mutation_rate - config.min_mutation_rate) * div_ratio

        order = np.argsort(fitness)[::-1]
        pop, fitness = pop[order], fitness[order]

        yield (
            GenerationStats(
                generation=gen,
                best_fitness=fitness[0],
                avg_fitness=float(np.mean(fitness[np.isfinite(fitness)]))
                if np.any(np.isfinite(fitness)) else float("nan"),
                worst_fitness=float(fitness[np.isfinite(fitness)].min())
                if np.any(np.isfinite(fitness)) else float("nan"),
                diversity=diversity,
                mutation_rate=mut_rate,
                best_params=space.decode(pop[0]),
            ),
            pop.copy(),
            fitness.copy(),
        )

        if gen == config.generations - 1:
            break

        # Next generation: carry the elites, fill the rest by selection+crossover+mutation.
        new_pop = [pop[i].copy() for i in range(config.elitism)]
        while len(new_pop) < config.population_size:
            p1, p2 = select(pop, fitness), select(pop, fitness)
            if rng.random() < config.crossover_prob:
                c1, c2 = uniform_crossover(p1, p2, rng)
            else:
                c1, c2 = p1.copy(), p2.copy()
            c1 = gaussian_mutate(c1, space, mut_rate, config.mutation_scale, rng)
            c2 = gaussian_mutate(c2, space, mut_rate, config.mutation_scale, rng)
            new_pop.append(c1)
            if len(new_pop) < config.population_size:
                new_pop.append(c2)

        pop = np.array(new_pop)
        fitness = np.array([evaluator.evaluate(ind)[0] for ind in pop])


# ────────────────────────────────────────────────────────────────────────────
# IS/OOS driver + result assembly
# ────────────────────────────────────────────────────────────────────────────
def split_is_oos(prices: pd.DataFrame, oos_fraction: float = 0.3) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Chronological IS/OOS split. The last ``oos_fraction`` is held out."""
    if not 0 < oos_fraction < 1:
        raise ValueError("oos_fraction must be in (0, 1)")
    n = len(prices)
    cut = int(round(n * (1 - oos_fraction)))
    cut = max(1, min(cut, n - 1))
    return prices.iloc[:cut], prices.iloc[cut:]


def _haircut_pct(is_fit: float, oos_fit: float) -> float | None:
    """IS→OOS fitness drop in %, positive = OOS worse than IS.

    Returns ``None`` when IS fitness is non-positive (the ratio is meaningless).
    """
    if not (math.isfinite(is_fit) and math.isfinite(oos_fit)) or is_fit <= 0:
        return None
    return float((is_fit - oos_fit) / abs(is_fit) * 100.0)


@dataclass
class GAResult:
    """Everything the optimizer learned, ready for JSON serialization."""

    param_names: list[str]
    history: list[GenerationStats]
    top: list[dict] = field(default_factory=list)  # top-N param sets, IS vs OOS
    best: dict | None = None
    config: dict = field(default_factory=dict)
    fitness_metric: str = "sharpe_dd"
    oos_fraction: float = 0.3
    haircut_reject_pct: float = 50.0

    def to_dict(self) -> dict:
        return {
            "param_names": self.param_names,
            "fitness_metric": self.fitness_metric,
            "oos_fraction": self.oos_fraction,
            "haircut_reject_pct": self.haircut_reject_pct,
            "config": self.config,
            "history": [g.to_dict() for g in self.history],
            "top": self.top,
            "best": self.best,
        }


def _score_metrics(metrics: dict, fitness: FitnessFn) -> dict:
    """Slim, JSON-safe metrics bundle for the result matrix."""
    keep = ("sharpe", "cagr", "max_drawdown", "calmar", "annual_volatility", "n_trades")
    out = {k: _finite(metrics.get(k)) if k != "n_trades" else int(metrics.get(k, 0) or 0)
           for k in keep}
    out["fitness"] = _finite(fitness(metrics))
    return out


def run_ga(
    prices: pd.DataFrame,
    space: ParamSpace,
    strategy: StrategyFn = ma_crossover_strategy,
    config: GAConfig | None = None,
    fitness_metric: str = "sharpe_dd",
    oos_fraction: float = 0.3,
    haircut_reject_pct: float = 50.0,
    cost_model: CostModel | None = None,
    top_n: int = 5,
    on_generation: Callable[[GenerationStats], None] | None = None,
) -> GAResult:
    """Optimize ``strategy`` parameters with the GA under an IS/OOS protocol.

    Fitness is maximized ONLY on the in-sample slice. The final population's unique
    genomes are then re-scored on the out-of-sample slice; each of the ``top_n``
    sets carries its IS metrics, OOS metrics and the IS→OOS haircut, flagged
    ``overfit`` when the haircut exceeds ``haircut_reject_pct``.

    Args:
        on_generation: optional callback fired after every generation with its
            :class:`GenerationStats` — used to stream the live convergence chart.
    """
    config = config or GAConfig()
    fitness = FITNESS_FUNCTIONS.get(fitness_metric)
    if fitness is None:
        raise ValueError(f"unknown fitness_metric '{fitness_metric}'")

    is_prices, oos_prices = split_is_oos(prices, oos_fraction)
    is_eval = Evaluator(is_prices, space, strategy, fitness, cost_model)
    oos_eval = Evaluator(oos_prices, space, strategy, fitness, cost_model)

    history: list[GenerationStats] = []
    final_pop: np.ndarray | None = None
    for stats, pop, _fit in evolve(is_eval, space, config):
        history.append(stats)
        if on_generation is not None:
            on_generation(stats)
        final_pop = pop

    # Rank the unique converged genomes by IS fitness, score each on IS + OOS.
    seen: set[tuple] = set()
    ranked: list[dict] = []
    for vec in final_pop:  # already best-first
        params = space.decode(vec)
        key = tuple(round(params[n], 6) for n in space.names)
        if key in seen:
            continue
        seen.add(key)
        is_fit, is_metrics = is_eval.evaluate(vec)
        oos_fit, oos_metrics = oos_eval.evaluate(vec)
        ranked.append({
            "params": params,
            "is": _score_metrics(is_metrics, fitness),
            "oos": _score_metrics(oos_metrics, fitness),
            "haircut_pct": _haircut_pct(is_fit, oos_fit),
            "overfit": bool(_is_overfit(is_fit, oos_fit, haircut_reject_pct)),
        })
        if len(ranked) >= top_n:
            break

    result = GAResult(
        param_names=space.names,
        history=history,
        top=ranked,
        best=ranked[0] if ranked else None,
        config={
            "population_size": config.population_size,
            "generations": config.generations,
            "selection": config.selection,
            "crossover_prob": config.crossover_prob,
            "base_mutation_rate": config.base_mutation_rate,
            "min_mutation_rate": config.min_mutation_rate,
            "elitism": config.elitism,
            "seed": config.seed,
        },
        fitness_metric=fitness_metric,
        oos_fraction=oos_fraction,
        haircut_reject_pct=haircut_reject_pct,
    )
    return result


def _is_overfit(is_fit: float, oos_fit: float, reject_pct: float) -> bool:
    hc = _haircut_pct(is_fit, oos_fit)
    return hc is not None and hc > reject_pct


def fitness_surface(
    prices: pd.DataFrame,
    space: ParamSpace,
    best_params: dict[str, float],
    axes: tuple[str, str],
    strategy: StrategyFn = ma_crossover_strategy,
    fitness_metric: str = "sharpe_dd",
    grid: int = 24,
    oos_fraction: float = 0.3,
    cost_model: CostModel | None = None,
) -> dict:
    """Sample an IS-fitness landscape over two parameters (the rest held at best).

    Produces the data for the 3-D parameter surface / heatmap: a ``grid × grid``
    matrix ``z[j][i]`` of in-sample fitness with ``axes[0]`` on x and ``axes[1]``
    on y. A broad bright plateau ⇒ a robust optimum; an isolated spike ⇒ a fragile,
    curve-fit one. The marker at ``best_params`` shows where the GA landed.
    """
    fitness = FITNESS_FUNCTIONS[fitness_metric]
    is_prices, _ = split_is_oos(prices, oos_fraction)
    ev = Evaluator(is_prices, space, strategy, fitness, cost_model)
    spec = {s.name: s for s in space.specs}
    sx, sy = spec[axes[0]], spec[axes[1]]

    xs = [sx.clip(v) for v in np.linspace(sx.low, sx.high, grid)]
    ys = [sy.clip(v) for v in np.linspace(sy.low, sy.high, grid)]
    xs = sorted(set(xs))
    ys = sorted(set(ys))

    base = dict(best_params)
    z: list[list[float | None]] = []
    for yv in ys:
        row: list[float | None] = []
        for xv in xs:
            params = dict(base)
            params[axes[0]], params[axes[1]] = xv, yv
            vec = np.array([params[n] for n in space.names], dtype=float)
            fit, _ = ev.evaluate(vec)
            row.append(_finite(fit))
        z.append(row)

    return {"x_name": axes[0], "y_name": axes[1], "x": xs, "y": ys, "z": z,
            "best_x": best_params.get(axes[0]), "best_y": best_params.get(axes[1])}
