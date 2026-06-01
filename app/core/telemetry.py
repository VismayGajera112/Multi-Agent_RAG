"""Optional OpenTelemetry tracing wiring.

Everything here is best-effort: if the OTel packages are missing or the
collector is unreachable, the app/worker keeps running. Traces are exported
over OTLP to the OpenTelemetry Collector, which fans them into its tracing
pipeline (see ``otel/otel-collector-config.yaml``).
"""

from __future__ import annotations

import logging

from app.core.config import settings

logger = logging.getLogger("app.telemetry")

_tracer_provider_configured = False


def _build_tracer_provider():
    """Create (once) and register a global TracerProvider + OTLP exporter."""
    global _tracer_provider_configured

    from opentelemetry import trace
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    if _tracer_provider_configured:
        return trace.get_tracer_provider()

    resource = Resource.create(
        {
            "service.name": settings.service_name,
            "deployment.environment": settings.environment,
        }
    )
    provider = TracerProvider(resource=resource)

    if settings.otel_exporter_otlp_protocol == "http/protobuf":
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
            OTLPSpanExporter,
        )

        exporter = OTLPSpanExporter(
            endpoint=f"{settings.otel_exporter_otlp_endpoint}/v1/traces"
        )
    else:
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
            OTLPSpanExporter,
        )

        exporter = OTLPSpanExporter(
            endpoint=settings.otel_exporter_otlp_endpoint, insecure=True
        )

    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    _tracer_provider_configured = True
    logger.info(
        "OpenTelemetry tracing enabled -> %s", settings.otel_exporter_otlp_endpoint
    )
    return provider


def instrument_fastapi(app) -> None:
    """Attach OTel auto-instrumentation to a FastAPI app (no-op on failure)."""
    if not settings.otel_enabled:
        return
    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

        _build_tracer_provider()
        FastAPIInstrumentor.instrument_app(app)
    except Exception as exc:  # pragma: no cover
        logger.warning("FastAPI OTel instrumentation skipped: %s", exc)


def instrument_celery() -> None:
    """Attach OTel auto-instrumentation to the Celery worker (no-op on failure)."""
    if not settings.otel_enabled:
        return
    try:
        from opentelemetry.instrumentation.celery import CeleryInstrumentor

        _build_tracer_provider()
        CeleryInstrumentor().instrument()
    except Exception as exc:  # pragma: no cover
        logger.warning("Celery OTel instrumentation skipped: %s", exc)
