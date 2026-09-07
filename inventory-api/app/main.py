from fastapi import FastAPI
from fastapi.responses import Response

from app.metrics.prometheus import (
    http_request_duration_seconds,
    http_requests_total,
    http_responses_total,
    metrics_response,
)

import time

from app.routers.servers import router as servers_router


app = FastAPI(
    title="DevOps Inventory API",
    description="API para gestionar un inventario de servidores",
    version="1.0.0",
)


@app.middleware("http")
async def metrics_middleware(request, call_next):
    start_time = time.perf_counter()

    response = await call_next(request)

    duration = time.perf_counter() - start_time

    if request.url.path != "/metrics":
        http_requests_total.labels(
            method=request.method,
            endpoint=request.url.path,
        ).inc()

        http_responses_total.labels(
            method=request.method,
            endpoint=request.url.path,
            status_code=response.status_code,
        ).inc()

        http_request_duration_seconds.labels(
            method=request.method,
            endpoint=request.url.path,
        ).observe(duration)

    return response

@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/")
def root():
    return {"message": "DevOps Inventory API"}


@app.get("/metrics")
def metrics():
    content, content_type = metrics_response()

    return Response(
        content=content,
        media_type=content_type.split(";")[0],
    )


app.include_router(servers_router)
