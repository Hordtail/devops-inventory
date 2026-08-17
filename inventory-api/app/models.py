from enum import Enum

from pydantic import BaseModel, Field, IPvAnyAddress


class Environment(str, Enum):
    development = "development"
    staging = "staging"
    production = "production"


class ServerStatus(str, Enum):
    running = "running"
    stopped = "stopped"
    maintenance = "maintenance"


class Server(BaseModel):
    id: int
    name: str
    ip: IPvAnyAddress
    environment: Environment
    status: ServerStatus
    location: str | None = None

    model_config = {
        "from_attributes": True
    }


class ServerCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    ip: IPvAnyAddress
    environment: Environment
    status: ServerStatus = ServerStatus.running
    location: str | None = Field(default=None, max_length=100)


class ServerUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    ip: IPvAnyAddress | None = None
    environment: Environment | None = None
    status: ServerStatus | None = None
    location: str | None = Field(default=None, max_length=100)