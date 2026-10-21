"""Configuration — every knob is an env var, documented in .env.example.

No settings framework: a dataclass read once at startup. If you can read this
file, you know everything MiniHermes can be configured to do.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()  # reads .env in the current directory, if present


def _default_home() -> Path:
    """Use the renamed state directory, while continuing to read old installs."""
    current = Path(".minihermes")
    legacy = Path(".waku")
    if current.exists() or not legacy.exists():
        return current
    return legacy


@dataclass
class Settings:
    # --- LLM: pick a provider, set its key. See minihermes/loop/models.py PROVIDERS.
    provider: str = field(default_factory=lambda: os.getenv("MINIHERMES_PROVIDER", "anthropic"))
    # Explicit overrides (optional): key, endpoint, and model ids. Left empty,
    # the provider's own key env var and default models are used.
    api_key: str = field(default_factory=lambda: os.getenv("MINIHERMES_API_KEY", ""))
    base_url: str | None = field(default_factory=lambda: os.getenv("MINIHERMES_BASE_URL") or None)
    model: str = field(default_factory=lambda: os.getenv("MINIHERMES_MODEL", ""))
    # Cheap model used by the retrieval gate and the consolidation summarizer.
    small_model: str = field(default_factory=lambda: os.getenv("MINIHERMES_SMALL_MODEL", ""))

    # --- Home: where MiniHermes keeps its state (memory DB, calendar, outbox, traces).
    # Defaults to ./.minihermes next to where you run it, so you can open every file
    # it writes. Local-first means you can always look.
    home: Path = field(default_factory=lambda: Path(os.getenv("MINIHERMES_HOME", str(_default_home()))))

    # --- Loop guardrails
    max_iterations: int = field(default_factory=lambda: int(os.getenv("MINIHERMES_MAX_ITERATIONS", "10")))
    # Headroom matters for REASONING models (kimi-k3, gpt-5.x, gemini-*-pro):
    # they spend output tokens thinking before the answer, so a low cap makes
    # them hit stop_reason=max_tokens mid-thought and return an EMPTY reply
    # (watched kimi-k3 do exactly that at 2048). 8192 leaves room to think AND
    # answer; it's a ceiling, not a target, so efficient models still cost the same.
    max_tokens: int = field(default_factory=lambda: int(os.getenv("MINIHERMES_MAX_TOKENS", "8192")))
    # Working memory is a SLIDING WINDOW (like context RAM): only the last N
    # turns go into the prompt. Older turns aren't lost — they're in state.db,
    # distilled into facts by consolidation, and pulled back by the retrieval
    # gate when relevant. Without this cap a long thread (esp. the always-on
    # Telegram session) resends its whole history every turn until it explodes.
    history_turns: int = field(default_factory=lambda: int(os.getenv("MINIHERMES_HISTORY_TURNS", "12")))

    # --- CRM read-only integration. Credentials stay in the backend environment.
    odoo_url: str = field(default_factory=lambda: os.getenv("ODOO_URL", ""))
    odoo_api_key: str = field(default_factory=lambda: os.getenv("ODOO_API_KEY", ""))
    odoo_database: str = field(default_factory=lambda: os.getenv("ODOO_DATABASE", ""))

    # --- Memory
    # Consolidate (distill chats into durable facts) only after N new exchanges.
    consolidate_every: int = field(default_factory=lambda: int(os.getenv("MINIHERMES_CONSOLIDATE_EVERY", "6")))
    retrieval_top_k: int = field(default_factory=lambda: int(os.getenv("MINIHERMES_RETRIEVAL_TOP_K", "4")))
    # 'sqlite' (default, zero setup) or 'supabase' (pgvector upgrade path — see launch-rag).
    semantic_store: str = field(default_factory=lambda: os.getenv("MINIHERMES_SEMANTIC_STORE", "sqlite"))
    # 'sqlite' (default, zero setup) or 'notion' (episodes live in a Notion database).
    episodic_store: str = field(default_factory=lambda: os.getenv("MINIHERMES_EPISODIC_STORE", "sqlite"))

    # --- Tools
    # Sync created events into Apple Calendar (a dedicated "MiniHermes" calendar)
    # via AppleScript. Opt-in because it writes to your real calendar app.
    apple_calendar: bool = field(
        default_factory=lambda: os.getenv("MINIHERMES_APPLE_CALENDAR", "") in ("1", "true", "yes")
    )
    # Give the agent read/write access to Apple Calendar, Mail, Reminders, Notes
    # (macOS; first use triggers the system Automation permission prompts).
    apple_tools: bool = field(
        default_factory=lambda: os.getenv("MINIHERMES_APPLE_TOOLS", "") in ("1", "true", "yes")
    )
    # Register the experimental tools (delegate_task -> pi sub-agent, ...). Env is
    # the global switch; the arena sets this per-race so a coding race can hand
    # work to pi WITHOUT flipping it on for the whole process.
    experimental: bool = field(
        default_factory=lambda: os.getenv("MINIHERMES_EXPERIMENTAL", "") in ("1", "true", "yes")
    )

    # --- Optional gateway
    telegram_token: str = field(default_factory=lambda: os.getenv("TELEGRAM_BOT_TOKEN", ""))

    # --- Tracing (JSONL always; OTel exports if an endpoint is set)
    otel_endpoint: str = field(
        default_factory=lambda: os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "")
    )

    def ensure_home(self) -> Path:
        self.home.mkdir(parents=True, exist_ok=True)
        (self.home / "traces").mkdir(exist_ok=True)
        (self.home / "outbox").mkdir(exist_ok=True)
        return self.home


def load_settings() -> Settings:
    return Settings()
