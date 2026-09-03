from fastapi import FastAPI
from fastapi.responses import Response

from app.metrics.prometheus import (
    http_requests_total,
    metrics_response,
)
from app.routers.servers import router as servers_router


app = FastAPI(
    title="DevOps Inventory API",
    description="API para gestionar un inventario de servidores",
    version="1.0.0",
)


@app.middleware("http")
async def metrics_middleware(request, call_next):
    response = await call_next(request)

    if request.url.path != "/metrics":
        http_requests_total.labels(
            method=request.method,
            endpoint=request.url.path,
        ).inc()

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