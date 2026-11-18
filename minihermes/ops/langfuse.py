"""Opt-in Langfuse export through the existing OpenTelemetry dependencies."""

from __future__ import annotations

import base64
import json
import logging
import os
from contextlib import contextmanager
from contextvars import ContextVar
from hashlib import sha256
from urllib.parse import urlsplit

logger = logging.getLogger(__name__)


class LangfuseTracing:
    def __init__(self):
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        public = os.getenv("LANGFUSE_PUBLIC_KEY", "").strip()
        secret = os.getenv("LANGFUSE_SECRET_KEY", "").strip()
        base_url = os.getenv("LANGFUSE_BASE_URL", "").strip().rstrip("/")
        url = urlsplit(base_url)
        local_http = url.scheme == "http" and url.hostname in {"localhost", "127.0.0.1", "::1"}
        if (not public or not secret or not url.hostname or url.username is not None
                or not (url.scheme == "https" or local_http) or url.query or url.fragment):
            raise ValueError("Set both Langfuse keys and an HTTPS base URL (HTTP for loopback).")
        auth = base64.b64encode(f"{public}:{secret}".encode()).decode("ascii")
        exporter = OTLPSpanExporter(
            endpoint=f"{base_url}/api/public/otel/v1/traces",
            headers={"authorization": f"Basic {auth}", "x-langfuse-ingestion-version": "4"},
            timeout=2,
        )
        # A private provider keeps Phoenix payloads and credentials away from Langfuse.
        self.provider = TracerProvider(resource=Resource({"service.name": "mini-hermes"}))
        self.provider.add_span_processor(BatchSpanProcessor(exporter))
        self.tracer = self.provider.get_tracer("minihermes.langfuse")
        self.environment = os.getenv("LANGFUSE_TRACING_ENVIRONMENT", "local")
        self.turn_attributes = ContextVar("langfuse_turn_attributes", default=None)

    @classmethod
    def from_env(cls):
        if os.getenv("MINIHERMES_LANGFUSE_TRACING", "").strip() != "1":
            return None
        try:
            return cls()
        except ImportError:
            logger.warning("Langfuse tracing requires the mini-hermes[tracing] extra.")
        except ValueError:
            logger.warning("Langfuse tracing needs both project keys and a valid base URL.")
        return None

    @contextmanager
    def turn(self, home, session_id, source, message):
        identity = sha256(f"{home.resolve()}\0{session_id}".encode()).hexdigest()
        token = self.turn_attributes.set({
            "langfuse.session.id": f"minihermes-{identity}",
            "langfuse.trace.name": "minihermes-chat-turn",
            "langfuse.environment": self.environment,
            "langfuse.trace.metadata.source": source if source in {
                "cli", "dashboard", "voice", "telegram", "compare",
            } else "other",
        })
        try:
            with self.span("minihermes-chat-turn", "agent", root=True) as fields:
                fields["input"] = {"message_chars": len(message)}
                yield fields
        finally:
            self.turn_attributes.reset(token)

    @contextmanager
    def span(self, name, kind, *, root=False):
        from opentelemetry.context import Context
        from opentelemetry.trace import Status, StatusCode

        fields = {}
        attributes = self.turn_attributes.get()
        if attributes is None:
            yield fields
            return
        with self.tracer.start_as_current_span(
            name, context=Context() if root else None,
            attributes={**attributes, "langfuse.observation.type": kind},
            record_exception=False, set_status_on_exception=False,
        ) as span:
            try:
                yield fields
            except Exception:
                span.set_status(Status(StatusCode.ERROR))
                raise
            finally:
                for key, value in fields.items():
                    span.set_attribute(
                        f"langfuse.observation.{key}",
                        value if isinstance(value, str) else json.dumps(value),
                    )
