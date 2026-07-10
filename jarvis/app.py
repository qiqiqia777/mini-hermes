"""Wiring — builds one Jarvis from its parts. Gateways call `respond()`.

This file is the assembly diagram in code: config → db → tools → memory →
session → loop. If you want to understand the repo in one place, start here.
"""

from __future__ import annotations

from jarvis.config import Settings, load_settings
from jarvis.db import connect
from jarvis.loop.agent import LoopResult, Observer, run_loop
from jarvis.loop.models import get_client
from jarvis.runtime.session import Session
from jarvis.tools import build_registry


class Jarvis:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or load_settings()
        self.settings.ensure_home()
        self.conn = connect(self.settings.home)
        self.client = get_client(self.settings)
        self.tools = build_registry(self.conn, self.settings)

        # Memory is optional wiring: without it Jarvis still works, it just
        # forgets — which is exactly the "before" state the video contrasts.
        try:
            from jarvis.memory import Memory

            self.memory = Memory(self.conn, self.settings, self.client)
        except ImportError:
            self.memory = None
        self.session = Session(self.settings, memory=self.memory)

    def respond(self, user_message: str, observer: Observer | None = None) -> LoopResult:
        """One full turn: assemble working memory → run the loop → persist."""
        system = self.session.build_system(user_message, notify=observer)
        messages = list(self.session.history) + [{"role": "user", "content": user_message}]

        result = run_loop(
            client=self.client,
            model=self.settings.model,
            system=system,
            messages=messages,
            tools=self.tools,
            max_iterations=self.settings.max_iterations,
            max_tokens=self.settings.max_tokens,
            observer=observer,
        )

        self.session.add_exchange(user_message, result.reply)
        if self.memory is not None:
            self.memory.maybe_consolidate(notify=observer)
        return result
