from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Histogram,
    generate_latest,
)


http_requests_total = Counter(
    "http_requests_total",
    "Total number of HTTP requests",
    ["method", "endpoint"],
)


http_responses_total = Counter(
    "http_responses_total",
    "Total number of HTTP responses",
    ["method", "endpoint", "status_code"],
)


http_request_duration_seconds = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "endpoint"],
)


def metrics_response():
    return generate_latest(), CONTENT_TYPE_LATEST
