from pydantic import BaseModel


class Server(BaseModel):
    id: int
    name: str
    ip: str
    environment: str
    status: str

    model_config = {
        "from_attributes": True
    }


class ServerCreate(BaseModel):
    name: str
    ip: str
    environment: str
    status: str = "running"


class ServerUpdate(BaseModel):
    name: str | None = None
    ip: str | None = None
    environment: str | None = None
    status: str | None = None