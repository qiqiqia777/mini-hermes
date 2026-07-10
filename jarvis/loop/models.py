"""Model access — one client, any Anthropic-compatible endpoint.

Anthropic's Messages API shape is also served by Moonshot/Kimi, GLM and others,
so "multi-provider" here is just a base_url override — no adapter classes.
(Pattern borrowed from launch-DeepResearch-Backend's model_service, minus LangChain.)
"""

from __future__ import annotations

import anthropic

from jarvis.config import Settings


def get_client(settings: Settings) -> anthropic.Anthropic:
    if not settings.api_key:
        raise SystemExit(
            "No ANTHROPIC_API_KEY set. Copy .env.example to .env and add your key."
        )
    kwargs: dict = {"api_key": settings.api_key}
    if settings.base_url:
        kwargs["base_url"] = settings.base_url
    return anthropic.Anthropic(**kwargs)
