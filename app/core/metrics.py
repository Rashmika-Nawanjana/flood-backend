from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
from fastapi import Response
import time

# --- HTTP metrics (labeled per service) ---
http_requests_total = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["service", "method", "endpoint", "status_code"],
)

http_request_duration_seconds = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency",
    ["service", "method", "endpoint"],
    buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0],
)

http_requests_in_progress = Gauge(
    "http_requests_in_progress",
    "HTTP requests currently in progress",
    ["service"],
)


def make_metrics_middleware(service_name: str):
    """Returns a Starlette middleware class pre-bound to the given service name."""
    from starlette.middleware.base import BaseHTTPMiddleware
    from starlette.requests import Request

    class PrometheusMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request: Request, call_next):
            # Skip the /metrics endpoint itself to avoid self-instrumentation noise
            if request.url.path == "/metrics":
                return await call_next(request)

            endpoint = request.url.path
            method = request.method
            http_requests_in_progress.labels(service=service_name).inc()
            start = time.perf_counter()
            try:
                response = await call_next(request)
                status_code = str(response.status_code)
            except Exception:
                status_code = "500"
                raise
            finally:
                duration = time.perf_counter() - start
                http_requests_in_progress.labels(service=service_name).dec()
                http_requests_total.labels(
                    service=service_name,
                    method=method,
                    endpoint=endpoint,
                    status_code=status_code,
                ).inc()
                http_request_duration_seconds.labels(
                    service=service_name,
                    method=method,
                    endpoint=endpoint,
                ).observe(duration)

            return response

    return PrometheusMiddleware


def metrics_endpoint():
    """FastAPI route handler that returns Prometheus text format."""
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
