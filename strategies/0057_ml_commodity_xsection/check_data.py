"""Phase-0/1 gate check: feature coverage + design-matrix shapes."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from quantlab.commodity_features import assemble_design_matrix, build_feature_panels

panels = build_feature_panels()
for name, p in panels["features"].items():
    cov = p.notna().sum(axis=1)
    print(f"{name:12s} mean coverage {cov.mean():.1f}/17, last {cov.iloc[-1]}")
macro = panels["macro"]
print("macro cols:", list(macro.columns), "| rows with NaN:", int(macro.isna().any(axis=1).sum()))

for h in (5, 21, 63):
    df = assemble_design_matrix(panels, horizon=h)
    dates = df.index.get_level_values("date")
    print(f"h={h}: {len(df):,} rows, {dates.nunique()} dates, "
          f"{dates.min().date()}..{dates.max().date()}")

# Gate: carry computable for >=15 roots on recent dates.
carry_cov = panels["features"]["carry"].iloc[-252:].notna().sum(axis=1)
assert carry_cov.median() >= 15, f"carry coverage too low: {carry_cov.median()}"
print("GATE OK: carry/basis computable for", int(carry_cov.median()), "roots (last year median)")
