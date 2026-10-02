from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

_requests_instrumented = False


def setup_tracer(service_name: str):
    """Khởi tạo OpenTelemetry TracerProvider và xuất spans về Jaeger qua OTLP HTTP (:4318).

    Tự động đính kèm W3C traceparent header vào tất cả requests gọi đi (outgoing requests).
    """
    global _requests_instrumented

    resource = Resource.create(
        {
            "service.name": service_name,
            "deployment.environment": "development",
        }
    )

    provider = TracerProvider(resource=resource)
    from config import JAEGER_OTLP_ENDPOINT
    otlp_exporter = OTLPSpanExporter(endpoint=JAEGER_OTLP_ENDPOINT)
    processor = BatchSpanProcessor(otlp_exporter)
    provider.add_span_processor(processor)

    try:
        trace.set_tracer_provider(provider)
    except Exception:
        pass

    if not _requests_instrumented:
        try:
            RequestsInstrumentor().instrument()
            _requests_instrumented = True
        except Exception as e:
            print(f"[Tracing] RequestsInstrumentor error: {e}")

    print(f"[Tracing] OpenTelemetry initialized for '{service_name}' -> Jaeger :4318")
    return trace.get_tracer(service_name)


def instrument_fastapi_app(app):
    """Gắn middleware OpenTelemetry tự động vào FastAPI app.

    Đọc W3C traceparent từ request gửi đến và tạo server span tương ứng.
    """
    try:
        FastAPIInstrumentor.instrument_app(app)
        print("[Tracing] FastAPI app instrumented successfully.")
    except Exception as e:
        print(f"[Tracing] FastAPI instrument error: {e}")
