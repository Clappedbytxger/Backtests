"""Quant-OS autonomous research agent (Phase 4).

Hard-walled by design: the agent writes code, runs backtests and commits — but
ONLY on an isolated ``agent/*`` branch, NEVER on ``main``/``master``, NEVER
pushing, and with NO access to live-order tools. Live execution stays the
deterministic 0108 bot (no LLM in the order path). See :mod:`agent.guardrails`.
"""
