"""Configuration — every knob is an env var, documented in .env.example.

No settings framework: a dataclass read once at startup. If you can read this
file, you know everything Waku can be configured to do.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()  # reads .env in the current directory, if present


@dataclass
class Settings:
    # --- LLM: pick a provider, set its key. See waku/loop/models.py PROVIDERS.
    provider: str = field(default_factory=lambda: os.getenv("WAKU_PROVIDER", "anthropic"))
    # Explicit overrides (optional): key, endpoint, and model ids. Left empty,
    # the provider's own key env var and default models are used.
    api_key: str = field(default_factory=lambda: os.getenv("WAKU_API_KEY", ""))
    base_url: str | None = field(default_factory=lambda: os.getenv("WAKU_BASE_URL") or None)
    model: str = field(default_factory=lambda: os.getenv("WAKU_MODEL", ""))
    # Cheap model used by the retrieval gate and the consolidation summarizer.
    small_model: str = field(default_factory=lambda: os.getenv("WAKU_SMALL_MODEL", ""))

    # --- Home: where Waku keeps its state (memory DB, calendar, outbox, traces).
    # Defaults to ./.waku next to where you run it, so you can open every file
    # it writes. Local-first means you can always look.
    home: Path = field(default_factory=lambda: Path(os.getenv("WAKU_HOME", ".waku")))

    # --- Loop guardrails
    max_iterations: int = field(default_factory=lambda: int(os.getenv("WAKU_MAX_ITERATIONS", "10")))
    max_tokens: int = field(default_factory=lambda: int(os.getenv("WAKU_MAX_TOKENS", "2048")))

    # --- Memory
    # Consolidate (distill chats into durable facts) only after N new exchanges.
    consolidate_every: int = field(default_factory=lambda: int(os.getenv("WAKU_CONSOLIDATE_EVERY", "6")))
    retrieval_top_k: int = field(default_factory=lambda: int(os.getenv("WAKU_RETRIEVAL_TOP_K", "4")))
    # 'sqlite' (default, zero setup) or 'supabase' (pgvector upgrade path — see launch-rag).
    semantic_store: str = field(default_factory=lambda: os.getenv("WAKU_SEMANTIC_STORE", "sqlite"))

    # --- Tools
    # Sync created events into Apple Calendar (a dedicated "Waku" calendar)
    # via AppleScript. Opt-in because it writes to your real calendar app.
    apple_calendar: bool = field(
        default_factory=lambda: os.getenv("WAKU_APPLE_CALENDAR", "") in ("1", "true", "yes")
    )
    # Give the agent read/write access to Apple Calendar, Mail, Reminders, Notes
    # (macOS; first use triggers the system Automation permission prompts).
    apple_tools: bool = field(
        default_factory=lambda: os.getenv("WAKU_APPLE_TOOLS", "") in ("1", "true", "yes")
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
