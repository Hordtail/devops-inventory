from prometheus_client import Counter, generate_latest, CONTENT_TYPE_LATEST


http_requests_total = Counter(
    "http_requests_total",
    "Total number of HTTP requests",
    ["method", "endpoint"],
)


def metrics_response():
    return generate_latest(), CONTENT_TYPE_LATEST
