"""mini-hermes — a minimal, transparent, local-first MiniHermes.

Four pillars, one module each:
  harness  → minihermes/runtime + minihermes/gateway  (scaffolding around the raw LLM)
  loop     → minihermes/loop                      (observe → reason → act → repeat)
  memory   → minihermes/memory                    (procedural / semantic / episodic)
  ops      → minihermes/ops + evals/              (trace → eval → gate → release)
"""

__version__ = "0.1.0"
