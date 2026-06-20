"""Command-line entry point for the autonomous research agent.

    python -m agent "hypothesis text"                 # full cycle (uses config backend)
    python -m agent "hypothesis" --backend mock        # no model (smoke / scaffold only)
    python -m agent "hypothesis" --dry-run             # generate run.py, do not execute/commit
    python -m agent "hypothesis" --slug my-exp

Always runs on an isolated ``agent/<slug>`` branch and never pushes.
"""

from __future__ import annotations

import argparse
import json

from .llm import get_backend
from .loop import run_research_cycle


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="agent", description="Autonomous quant research cycle")
    ap.add_argument("hypothesis", help="the hypothesis to test")
    ap.add_argument("--slug", default=None, help="branch/folder slug (default: derived)")
    ap.add_argument("--backend", default=None, help="auto|mock|llamacpp|mlx (default: config)")
    ap.add_argument("--model", default=None, help="model path/id for a real backend")
    ap.add_argument("--dry-run", action="store_true", help="generate run.py only; no execute/commit")
    args = ap.parse_args(argv)

    backend = None
    if args.backend:
        kw = {"model_path": args.model} if args.backend == "llamacpp" and args.model else \
             ({"model": args.model} if args.backend == "mlx" and args.model else {})
        backend = get_backend(args.backend, **kw)

    res = run_research_cycle(args.hypothesis, backend=backend, slug=args.slug, dry_run=args.dry_run)
    printable = {k: v for k, v in res.items() if k != "stdout_tail"}
    print(json.dumps(printable, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
