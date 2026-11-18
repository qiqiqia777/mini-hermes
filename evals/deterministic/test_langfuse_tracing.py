"""Exercise the real OTLP exporter against a local receiver with synthetic data."""

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread

import pytest

from evals.helpers import ScriptedClient, make_minihermes, response, text_block, tool_block
from minihermes.ops.langfuse import LangfuseTracing
from minihermes.tools.registry import Tool


def test_langfuse_requires_opt_in_and_credentials(monkeypatch, caplog):
    monkeypatch.setenv("MINIHERMES_LANGFUSE_TRACING", "0")
    assert LangfuseTracing.from_env() is None
    assert not caplog.records
    monkeypatch.setenv("MINIHERMES_LANGFUSE_TRACING", "1")
    monkeypatch.delenv("LANGFUSE_SECRET_KEY", raising=False)
    assert LangfuseTracing.from_env() is None
    assert "Langfuse tracing" in caplog.text


def test_langfuse_exports_nested_metadata_and_errors(tmp_path, monkeypatch):
    otlp = pytest.importorskip("opentelemetry.proto.collector.trace.v1.trace_service_pb2")
    pytest.importorskip("opentelemetry.exporter.otlp.proto.http.trace_exporter")
    requests = []

    class Receiver(BaseHTTPRequestHandler):
        def do_POST(self):
            body = self.rfile.read(int(self.headers["Content-Length"]))
            requests.append((self.path, self.headers, body))
            self.send_response(200)
            self.end_headers()

    with ThreadingHTTPServer(("127.0.0.1", 0), Receiver) as server:
        worker = Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            monkeypatch.setenv("MINIHERMES_LANGFUSE_TRACING", "1")
            monkeypatch.setenv("LANGFUSE_BASE_URL", f"http://127.0.0.1:{server.server_port}")
            monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "public")
            monkeypatch.setenv("LANGFUSE_SECRET_KEY", "secret")
            monkeypatch.setenv("LANGFUSE_TRACING_ENVIRONMENT", "test")
            monkeypatch.setenv("OTEL_EXPORTER_OTLP_TRACES_COMPRESSION", "none")
            gate = response([text_block('{"retrieve": true, "query": "private-query"}')])
            call = response([tool_block("example", {"data": "private-argument"})], "tool_use")
            call.model = "actual-model"
            call.usage.input_tokens = 17
            call.usage.output_tokens = 4
            client = ScriptedClient([gate, call, response([text_block("private-reply")]), gate])

            def stream_failure(**kwargs):
                raise RuntimeError("private-exception")

            client.messages.stream = stream_failure
            app = make_minihermes(tmp_path, client=client, model="requested-model",
                                  small_model="gate-model", otel_endpoint="", consolidate_every=99,
                                  semantic_store="sqlite", episodic_store="sqlite")
            try:
                app.session.start_new("private-session")
                app.tools.register(Tool("example", "Example", {}, lambda **kw: "Error: private-tool"))
                assert app.respond("private-message", source="dashboard", stream=True).reply == "private-reply"
                with pytest.raises(IndexError):
                    app.respond("private-failed-message", source="dashboard")
            finally:
                app.close()
        finally:
            server.shutdown()
            worker.join()

    spans = []
    for path, headers, body in requests:
        assert path == "/api/public/otel/v1/traces"
        assert headers["Authorization"] == "Basic cHVibGljOnNlY3JldA=="
        assert headers["x-langfuse-ingestion-version"] == "4"
        assert b"private-" not in body
        exported = otlp.ExportTraceServiceRequest.FromString(body)
        for resource in exported.resource_spans:
            for scope in resource.scope_spans:
                spans.extend(scope.spans)

    def attr(span, key):
        return next(item.value.string_value for item in span.attributes if item.key == key)

    roots = [span for span in spans if span.name == "minihermes-chat-turn"]
    assert len(roots) == 2
    root = next(span for span in roots if span.status.code == 0)
    assert not root.parent_span_id
    assert json.loads(attr(root, "langfuse.observation.output"))["iterations"] == 2
    assert any(span.status.code == 2 for span in roots)
    assert len({attr(span, "langfuse.session.id") for span in spans}) == 1
    assert {attr(span, "langfuse.environment") for span in spans} == {"test"}

    children = [span for span in spans if span.parent_span_id == root.span_id]
    assert [span.name for span in sorted(children, key=lambda span: span.start_time_unix_nano)] == [
        "memory-gate", "memory-search", "model-stream", "model-request", "example",
        "model-stream", "model-request",
    ]
    generation = next(span for span in children if span.name == "model-request")
    assert attr(generation, "langfuse.observation.type") == "generation"
    assert attr(generation, "langfuse.observation.model.name") == "actual-model"
    assert json.loads(attr(generation, "langfuse.observation.usage_details")) == {"input": 17, "output": 4}
    tool = next(span for span in children if span.name == "example")
    assert attr(tool, "langfuse.observation.type") == "tool"
    assert attr(tool, "langfuse.observation.level") == "ERROR"
    guardrail = next(span for span in children if span.name == "memory-gate")
    assert any(span.parent_span_id == guardrail.span_id and span.name == "memory-gate-model"
               for span in spans)
    assert "private-message" in app.tracer.path.read_text(encoding="utf-8")
