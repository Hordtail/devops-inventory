from pydantic import BaseModel


class Server(BaseModel):
    id: int
    name: str
    ip: str
    environment: str
    status: str
    location: str | None = None

    model_config = {
        "from_attributes": True
    }


class ServerCreate(BaseModel):
    name: str
    ip: str
    environment: str
    status: str = "running"
    location: str | None = None


class ServerUpdate(BaseModel):
    name: str | None = None
    ip: str | None = None
    environment: str | None = None
    status: str | None = None
    location: str | None = None