# OpenTelemetry Integration

This Django starter kit includes opt-in OpenTelemetry support for distributed tracing. The integration works with any OTLP-compatible backend (SigNoz, Grafana Tempo, Jaeger, Datadog, etc.).

## Packages

Only the essential instrumentors are included:

- `opentelemetry-sdk`
- `opentelemetry-exporter-otlp`
- `opentelemetry-instrumentation-django`
- `opentelemetry-instrumentation-psycopg`

## Configuration

OpenTelemetry is **disabled by default**. Enable it by setting environment variables in your `.env` file:

```env
OTEL_ENABLED=true
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
OTEL_SERVICE_NAME=django-starter-kit
OTEL_SERVICE_VERSION=1.0.0
```

Initialization happens in `config/otel.py`, called from `config/asgi.py` at startup.

## What's Instrumented

When enabled, the following are automatically traced:

- **Django** — HTTP requests and responses
- **psycopg** — PostgreSQL database queries

That's it. No extra instrumentors for urllib, threading, asyncio, system metrics, etc. — add them only if you need them.

## Using with SigNoz

For self-hosted SigNoz setup, see: [signoz.io/docs/install/self-host](https://signoz.io/docs/install/self-host/)

## Using with Other Backends

Update `OTEL_EXPORTER_OTLP_ENDPOINT` to point to your backend. If authentication is required:

```env
OTEL_EXPORTER_OTLP_HEADERS=authorization=Bearer your-token-here
```

## Custom Spans

Add manual tracing to your own code:

```python
from opentelemetry import trace

tracer = trace.get_tracer(__name__)

with tracer.start_as_current_span("my-operation"):
    # your code here
    pass
```

## Disabling

Set `OTEL_ENABLED=false` or remove the variable entirely. When disabled, no OTel code runs — the instrumentors are only imported and activated when `OTEL_ENABLED=true`.

## Troubleshooting

1. **No traces appearing** — check that `OTEL_ENABLED=true` is set and the endpoint is reachable.
2. **Connection errors** — verify the OTLP endpoint port (default `4317` for gRPC) and that the backend is running.
3. **Debug logging** — set `OTEL_LOG_LEVEL=DEBUG` in your environment.
