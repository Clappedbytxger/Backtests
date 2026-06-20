# Quant-OS Autonomous Research Agent (Phase 4)

A local, hard-walled agent that runs the research loop end to end —
**hypothesis → code → backtest → REPORT → commit** — so ideas from the backlog can
be triaged automatically. It is **research-only**.

## Safety model (non-negotiable)

- **Isolated branch only.** Every cycle runs on an `agent/<slug>` branch; the agent
  refuses to operate on `main`/`master` (`agent.guardrails.assert_safe_branch`).
- **Never pushes.** All git goes through `safe_git`, an allow-list (`add/commit/
  checkout/branch/status/…`); `push/remote/reset/clean/rebase/pull/merge` are refused.
- **No live-order tools.** The agent cannot reach the OMS or any broker. Live
  execution stays the deterministic 0108 bot — **no LLM in the order path**.
- **Human merge review.** LLM-generated `run.py` is arbitrary code run in a
  subprocess; isolation + a human PR review before merge is the control.
- Generated strategies face the **same gates as human ones** (look-ahead tests,
  permutation/DSR, de-dup against `CATALOG.md`).

## Architecture

| Module | Role |
|--------|------|
| `agent/guardrails.py` | branch isolation, no-push allow-list, `agent_commit` |
| `agent/llm/` | `LLMBackend` + `MockBackend` (tests) + `LlamaCppBackend`/`MLXBackend` (lazy) + `get_backend` |
| `agent/rag/` | TF-IDF over `HYPOTHESES.csv`; de-dup against `CATALOG.md` |
| `agent/loop.py` | the research cycle |
| `agent/cli.py` | `python -m agent` |

## Usage

```bash
# scaffold only, no model, no execution/commit (safe smoke):
python -m agent "turn-of-month effect on bonds" --backend mock --dry-run

# full cycle with the configured local model:
python -m agent "pre-FOMC drift in gold"

# explicit local model:
python -m agent "wheat RV spread KC vs CHI" --backend llamacpp --model models/deepseek-coder.gguf
```

Output is a JSON summary (branch, strategy folder, metrics, catalog de-dup hits, commit SHA).

## Local model setup (one-time, optional)

The loop and all tests run with `--backend mock` and need **no model**. For real
inference:

```bash
pip install -e ".[agent]"     # llama-cpp-python (Windows) / mlx-lm (macOS)
```

- **Windows (AMD GPU):** download a GGUF (e.g. DeepSeek-Coder) and pass `--model path.gguf`,
  or set it in config. `llm_backend: llamacpp` in `config.yaml`.
- **macOS (Apple Silicon):** `llm_backend: mlx`; `--model mlx-community/<id>`.
- `llm_backend: auto` picks per platform.
