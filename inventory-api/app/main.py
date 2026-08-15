from fastapi import FastAPI

from app.routers.servers import router as servers_router


app = FastAPI(
    title="DevOps Inventory API",
    description="API para gestionar un inventario de servidores",
    version="1.0.0",
)


app.include_router(servers_router)


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.get("/")
def root():
    return {"message": "DevOps Inventory API"}