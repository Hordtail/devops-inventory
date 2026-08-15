from pydantic import BaseModel


class Server(BaseModel):
    id: int
    name: str
    ip: str
    environment: str
    status: str


class ServerCreate(BaseModel):
    name: str
    ip: str
    environment: str
    status: str = "running"


class ServerUpdate(BaseModel):
    name: str
    ip: str
    environment: str
    status: str
    