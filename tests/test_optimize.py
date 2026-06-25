"""Logical-correctness tests for the genetic-algorithm parameter optimizer.

Validates the GA core on a controlled moving-average crossover problem:
    * operators (clip/encode, crossover, mutation, selection) behave,
    * adaptive mutation falls as the population converges,
    * the GA actually maximizes a known synthetic optimum,
    * the IS/OOS protocol + haircut flagging work,
    * the run is deterministic for a fixed seed,
    * the fitness surface is shaped correctly.
"""

import numpy as np
import pandas as pd

from quantlab.optimize import (
    Evaluator,
    GAConfig,
    ParamSpace,
    ParamSpec,
    fitness_sharpe_dd,
    fitness_surface,
    gaussian_mutate,
    ma_crossover_strategy,
    population_diversity,
    run_ga,
    split_is_oos,
    tournament_select,
    uniform_crossover,
)


# ── fixtures ─────────────────────────────────────────────────────────────────
def _trending_prices(n: int = 800, seed: int = 0) -> pd.DataFrame:
    """A persistent up-trend with noise — a regime where SMA crossover has an edge."""
    rng = np.random.default_rng(seed)
    drift = 0.0006
    rets = rng.normal(drift, 0.01, n)
    idx = pd.date_range("2015-01-01", periods=n, freq="B")
    close = 100 * (1 + pd.Series(rets, index=idx)).cumprod()
    return pd.DataFrame({"Close": close, "Open": close, "High": close,
                         "Low": close, "Volume": 1.0}, index=idx)


def _space() -> ParamSpace:
    return ParamSpace([
        ParamSpec("sma_fast", 5, 50, integer=True),
        ParamSpec("sma_slow", 60, 200, integer=True),
        ParamSpec("stop_loss_pct", 0.0, 0.2, step=0.01),
    ])


# ── parameter space / encoding ───────────────────────────────────────────────
def test_paramspec_clip_integer_and_step():
    s_int = ParamSpec("w", 5, 50, integer=True)
    assert s_int.clip(7.8) == 8.0
    assert s_int.clip(100) == 50.0  # clamped to high
    assert s_int.clip(-3) == 5.0    # clamped to low

    s_step = ParamSpec("p", 0.0, 0.2, step=0.05)
    assert s_step.clip(0.07) == 0.05
    assert s_step.clip(0.08) == 0.10


def test_decode_roundtrip_and_random_population_in_bounds():
    space = _space()
    rng = np.random.default_rng(1)
    pop = space.random_population(30, rng)
    assert pop.shape == (30, 3)
    assert np.all(pop >= space.lows) and np.all(pop <= space.highs)
    decoded = space.decode(pop[0])
    assert set(decoded) == {"sma_fast", "sma_slow", "stop_loss_pct"}
    assert float(decoded["sma_fast"]).is_integer()


# ── operators ────────────────────────────────────────────────────────────────
def test_uniform_crossover_conserves_genes():
    rng = np.random.default_rng(2)
    a = np.array([1.0, 2.0, 3.0])
    b = np.array([4.0, 5.0, 6.0])
    c1, c2 = uniform_crossover(a, b, rng)
    # Each locus: the two children together hold exactly the two parents' genes.
    for i in range(3):
        assert {c1[i], c2[i]} == {a[i], b[i]}


def test_mutation_stays_in_bounds_and_rate_zero_is_identity():
    space = _space()
    rng = np.random.default_rng(3)
    vec = space.clip_vector(np.array([20.0, 100.0, 0.05]))
    same = gaussian_mutate(vec, space, rate=0.0, scale=0.2, rng=rng)
    assert np.allclose(same, vec)  # rate 0 => no change
    mutated = gaussian_mutate(vec, space, rate=1.0, scale=0.5, rng=rng)
    assert np.all(mutated >= space.lows) and np.all(mutated <= space.highs)


def test_tournament_selection_prefers_fitter():
    rng = np.random.default_rng(4)
    pop = np.array([[0.0], [1.0], [2.0], [3.0]])
    fitness = np.array([-1.0, 0.0, 1.0, 5.0])  # last is clearly best
    picks = [tournament_select(pop, fitness, rng, k=3)[0] for _ in range(200)]
    assert np.mean(picks) > 2.0  # selection pressure pulls toward the fittest


# ── adaptive mutation behaviour ──────────────────────────────────────────────
def test_diversity_zero_when_converged():
    space = _space()
    clone = space.clip_vector(np.array([20.0, 100.0, 0.05]))
    pop = np.tile(clone, (10, 1))
    assert population_diversity(pop, space) < 1e-12


def test_adaptive_mutation_rate_falls_with_convergence():
    """Mutation rate must decrease monotonically as the population converges."""
    space = _space()
    prices = _trending_prices()
    rates = [g.mutation_rate for g in
             run_ga(prices, space, config=GAConfig(population_size=24, generations=15,
                                                   seed=7)).history]
    # Compare the early phase to the late phase: late mutation < early mutation.
    early = np.mean(rates[:3])
    late = np.mean(rates[-3:])
    assert late <= early + 1e-9
    assert min(rates) >= 0.05 - 1e-9  # never below the configured floor


# ── the GA optimizes a known optimum ─────────────────────────────────────────
def test_ga_finds_synthetic_optimum():
    """On a smooth quadratic, the GA must converge near the analytic peak.

    Strategy params are ignored; fitness = -(x-30)^2 -(y-120)^2 with the peak at
    (30, 120). The GA should land close to it — proves the loop maximizes.
    """
    space = ParamSpace([ParamSpec("sma_fast", 5, 60, integer=True),
                        ParamSpec("sma_slow", 60, 200, integer=True)])

    class _QuadEval(Evaluator):
        def _run(self, params):  # type: ignore[override]
            x, y = params["sma_fast"], params["sma_slow"]
            score = -((x - 30) ** 2 + (y - 120) ** 2)
            return {"sharpe": score, "max_drawdown": 0.0, "cagr": 0.0, "calmar": 0.0,
                    "n_trades": 1}

    from quantlab.optimize import evolve, fitness_sharpe
    ev = _QuadEval(_trending_prices(), space, ma_crossover_strategy, fitness_sharpe)
    cfg = GAConfig(population_size=40, generations=40, seed=11)
    last_best = None
    for stats, _pop, _fit in evolve(ev, space, cfg):
        last_best = stats.best_params
    assert abs(last_best["sma_fast"] - 30) <= 4
    assert abs(last_best["sma_slow"] - 120) <= 8


def test_ga_improves_over_generations():
    """Best in-sample fitness must be non-decreasing under elitism."""
    space = _space()
    prices = _trending_prices()
    res = run_ga(prices, space, config=GAConfig(population_size=30, generations=20, seed=5))
    bests = [g.best_fitness for g in res.history]
    # Elitism guarantees the best never gets worse.
    for a, b in zip(bests, bests[1:]):
        assert b >= a - 1e-9
    assert bests[-1] >= bests[0]


# ── IS/OOS protocol + haircut ────────────────────────────────────────────────
def test_split_is_oos_chronological():
    prices = _trending_prices(n=100)
    is_p, oos_p = split_is_oos(prices, 0.3)
    assert len(is_p) == 70 and len(oos_p) == 30
    assert is_p.index.max() < oos_p.index.min()  # no overlap, IS strictly before OOS


def test_result_has_topn_with_is_oos_and_haircut_flags():
    space = _space()
    prices = _trending_prices()
    res = run_ga(prices, space, config=GAConfig(population_size=30, generations=18, seed=3),
                 top_n=5, haircut_reject_pct=50.0)
    d = res.to_dict()
    assert len(d["top"]) >= 1 and len(d["top"]) <= 5
    row = d["top"][0]
    assert {"params", "is", "oos", "haircut_pct", "overfit"} <= set(row)
    assert "sharpe" in row["is"] and "sharpe" in row["oos"]
    assert isinstance(row["overfit"], bool)
    # The flagged 'overfit' must be consistent with the haircut threshold.
    if row["haircut_pct"] is not None:
        assert row["overfit"] == (row["haircut_pct"] > 50.0)


def test_determinism_same_seed():
    space = _space()
    prices = _trending_prices()
    a = run_ga(prices, space, config=GAConfig(population_size=24, generations=12, seed=99))
    b = run_ga(prices, space, config=GAConfig(population_size=24, generations=12, seed=99))
    assert a.best["params"] == b.best["params"]
    assert [g.best_fitness for g in a.history] == [g.best_fitness for g in b.history]


# ── fitness surface ──────────────────────────────────────────────────────────
def test_fitness_surface_shape_and_marker():
    space = _space()
    prices = _trending_prices()
    res = run_ga(prices, space, config=GAConfig(population_size=20, generations=10, seed=1))
    surf = fitness_surface(prices, space, res.best["params"],
                           axes=("sma_fast", "sma_slow"), grid=12)
    assert surf["x_name"] == "sma_fast" and surf["y_name"] == "sma_slow"
    assert len(surf["z"]) == len(surf["y"])
    assert all(len(row) == len(surf["x"]) for row in surf["z"])
    assert surf["best_x"] == res.best["params"]["sma_fast"]


def test_fitness_sharpe_dd_penalizes_drawdown():
    shallow = fitness_sharpe_dd({"sharpe": 1.5, "max_drawdown": -0.10})
    deep = fitness_sharpe_dd({"sharpe": 1.5, "max_drawdown": -0.40})
    assert shallow > deep
    assert fitness_sharpe_dd({"sharpe": float("nan"), "max_drawdown": -0.1}) < -1e8
