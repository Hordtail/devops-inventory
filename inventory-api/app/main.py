from fastapi import FastAPI

app = FastAPI(
    title="DevOps Inventory API",
    description="API para gestionar un inventario de servidores",
    version="1.0.0",
)


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.get("/")
def root():
    return {"message": "Hello DevOps!"}