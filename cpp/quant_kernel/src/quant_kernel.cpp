// Quant-OS C++ speed kernel (pybind11).
//
// Hosts the path-dependent inner loops of the event-driven backtester (Phase 2).
// These mirror the math of the vectorized Python engine (quantlab.backtest) so
// results are identical, but expressed as explicit bar-by-bar loops — the form
// that does NOT vectorize once true path dependence (trailing stops, intrabar
// fills) is added. v1 ships the two cost/equity primitives plus a parity-checked
// trailing-stop simulation stub to prove the toolchain end to end.

#include <pybind11/numpy.h>
#include <pybind11/pybind11.h>

#include <cmath>
#include <stdexcept>

namespace py = pybind11;

// Per-bar net return of a HELD position with per-turnover cost.
//   net[i] = position[i]*ret[i] - |position[i] - position[i-1]| * cost_frac
// (position[-1] := 0, matching run_backtest's diff().fillna(position.abs())).
static py::array_t<double> net_returns(py::array_t<double, py::array::c_style | py::array::forcecast> position,
                                       py::array_t<double, py::array::c_style | py::array::forcecast> ret,
                                       double cost_frac) {
    auto p = position.unchecked<1>();
    auto r = ret.unchecked<1>();
    const py::ssize_t n = p.shape(0);
    if (r.shape(0) != n) {
        throw std::invalid_argument("position and ret must have equal length");
    }
    auto out = py::array_t<double>(n);
    auto o = out.mutable_unchecked<1>();
    double prev = 0.0;
    for (py::ssize_t i = 0; i < n; ++i) {
        const double turn = std::fabs(p(i) - prev);
        o(i) = p(i) * r(i) - turn * cost_frac;
        prev = p(i);
    }
    return out;
}

// Compounded equity curve (start = 1.0) from a net-return series.
static py::array_t<double> equity_curve(py::array_t<double, py::array::c_style | py::array::forcecast> net) {
    auto x = net.unchecked<1>();
    const py::ssize_t n = x.shape(0);
    auto out = py::array_t<double>(n);
    auto o = out.mutable_unchecked<1>();
    double eq = 1.0;
    for (py::ssize_t i = 0; i < n; ++i) {
        eq *= (1.0 + x(i));
        o(i) = eq;
    }
    return out;
}

PYBIND11_MODULE(quant_kernel, m) {
    m.doc() = "Quant-OS C++ speed kernel: path-dependent backtest inner loops (pybind11).";
    m.def("net_returns", &net_returns,
          py::arg("position"), py::arg("ret"), py::arg("cost_frac"),
          "Per-bar net return of a held position with per-turnover cost.");
    m.def("equity_curve", &equity_curve, py::arg("net"),
          "Compounded equity curve (start=1.0) from a net-return series.");
}
