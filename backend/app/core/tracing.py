"""Minimal OpenTelemetry setup.

Spans wrap each pipeline stage so one document's journey through all five engines
is a single trace. Console exporter for now; swapping in an OTLP exporter to a
collector (Jaeger/Tempo) is a config change, not a code change — the
instrumentation in the pipeline stays identical.
"""

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    ConsoleSpanExporter,
)

_configured = False


def configure_tracing(service_name: str = "docintel") -> None:
    global _configured
    if _configured:
        return
    provider = TracerProvider(
        resource=Resource.create({"service.name": service_name})
    )
    provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
    trace.set_tracer_provider(provider)
    _configured = True


def get_tracer():
    return trace.get_tracer("docintel.pipeline")
