# quant_kernel — Quant-OS C++ speed kernel

Path-dependent inner loops of the event-driven backtester (Phase 2), exposed to
Python via **pybind11** and built with **CMake** (cross-platform: MSVC on
Windows, Clang on macOS). The functions mirror the math of the vectorized Python
engine (`quantlab.backtest`) exactly, so the C++ path is a drop-in accelerator,
not a different model — verified against NumPy in `tests/test_kernel.py`.

## Functions (v1)

| Function | Signature | Meaning |
|----------|-----------|---------|
| `net_returns` | `(position, ret, cost_frac) -> ndarray` | per-bar net return of a held position with per-turnover cost |
| `equity_curve` | `(net) -> ndarray` | compounded equity (start = 1.0) |

## Build

Requires a C++17 compiler (MSVC ≥ 2019 / Clang) — found automatically by CMake.

```bash
# from the repo root, into the project venv
.venv/Scripts/python.exe -m pip install --no-build-isolation ./cpp/quant_kernel
```

Windows note: scikit-build-core sets up the MSVC environment for the Ninja
generator automatically. To force the Visual Studio generator instead:

```bash
SKBUILD_CMAKE_ARGS="-GVisual Studio 17 2022;-Ax64" \
  .venv/Scripts/python.exe -m pip install --no-build-isolation ./cpp/quant_kernel
```

## Verify

```bash
.venv/Scripts/python.exe -m pytest tests/test_kernel.py -q
```

The kernel is optional: `test_kernel.py` skips itself if `quant_kernel` is not
installed, so the rest of the suite never depends on a native build.
