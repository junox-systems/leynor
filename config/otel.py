# config/otel.py
import logging
import os

from typing import Optional

logger = logging.getLogger(__name__)


def initialize_opentelemetry() -> Optional[object]:
    """
    Initialize OpenTelemetry tracing and log export for the Django application.

    Called from asgi.py (before Django loads) and manage.py. The SDK's built-in
    fork-awareness handles worker processes automatically via os.register_at_fork().

    Returns:
        TracerProvider: The initialized tracer provider or None if OTel is disabled.
    """
    otel_enabled = os.environ.get("OTEL_ENABLED", "").lower() in ("true", "1", "yes")

    if not otel_enabled:
        logger.info("OpenTelemetry not enabled, skipping initialization.")
        return None

    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.grpc._log_exporter import (
            OTLPLogExporter,
        )
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
            OTLPSpanExporter,
        )
        from opentelemetry.instrumentation.psycopg import PsycopgInstrumentor
        from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
        from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        resource = Resource.create(
            {
                "service.name": os.environ.get(
                    "OTEL_SERVICE_NAME", "django-starter-kit"
                ),
                "service.version": os.environ.get("OTEL_SERVICE_VERSION", "1.0.0"),
                "deployment.environment": os.environ.get("ENVIRONMENT", "development"),
            }
        )

        otlp_endpoint = os.environ.get(
            "OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317"
        )

        # Traces
        provider = TracerProvider(resource=resource)
        trace.set_tracer_provider(provider)
        otlp_exporter = OTLPSpanExporter(endpoint=otlp_endpoint, insecure=True)
        provider.add_span_processor(BatchSpanProcessor(otlp_exporter))

        # HTTP request spans are created by OpenTelemetryMiddleware in asgi.py.
        PsycopgInstrumentor().instrument()

        # Logs — forward stdlib logging to the OTLP endpoint.
        # Level: OTEL_LOG_LEVEL env override; defaults to DEBUG in development,
        # WARNING in production. Accepts TRACE, DEBUG, INFO, WARNING, ERROR.
        log_level_name = os.environ.get("OTEL_LOG_LEVEL", "").upper()
        if not log_level_name:
            log_level_name = (
                "DEBUG"
                if os.environ.get("ENVIRONMENT", "development") == "development"
                else "WARNING"
            )
        log_level = getattr(logging, log_level_name, logging.WARNING)
        if not isinstance(log_level, int):
            log_level = logging.WARNING

        log_provider = LoggerProvider(resource=resource)
        log_processor = BatchLogRecordProcessor(
            OTLPLogExporter(endpoint=otlp_endpoint, insecure=True)
        )
        log_provider.add_log_record_processor(log_processor)
        root_logger = logging.getLogger()
        # Root defaults to WARNING — lower it so INFO/DEBUG reach the handler.
        root_logger.setLevel(log_level)
        root_logger.addHandler(
            LoggingHandler(level=log_level, logger_provider=log_provider)
        )

        logger.info("OpenTelemetry initialized with endpoint: %s", otlp_endpoint)
        return provider

    except Exception:
        logger.exception("Failed to initialize OpenTelemetry")
        return None
