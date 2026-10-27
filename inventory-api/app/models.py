from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field, IPvAnyAddress, field_validator


class Environment(str, Enum):
    development = "development"
    staging = "staging"
    production = "production"


class ServerStatus(str, Enum):
    running = "running"
    stopped = "stopped"
    maintenance = "maintenance"


class StockMovementType(str, Enum):
    incoming = "IN"
    outgoing = "OUT"


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


class Item(BaseModel):
    id: int
    code: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=1, max_length=100)
    unit: str = Field(min_length=1, max_length=20)
    description: str | None = Field(default=None, max_length=4000)
    image_path: str | None = None
    active: bool = True
    quantity_available: int = Field(ge=0)
    minimum_stock: int = Field(ge=0)

    model_config = {
        "from_attributes": True
    }

    @field_validator("code", "name", "unit")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be empty or whitespace only")
        return value

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None


class ItemCreate(BaseModel):
    code: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=1, max_length=100)
    unit: str = Field(min_length=1, max_length=20)
    description: str | None = Field(default=None, max_length=4000)
    active: bool = True
    minimum_stock: int = Field(default=1, ge=0)

    model_config = {"extra": "forbid"}

    @field_validator("code", "name", "unit")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be empty or whitespace only")
        return value

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None


class ItemUpdate(BaseModel):
    code: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=1, max_length=100)
    unit: str = Field(min_length=1, max_length=20)
    description: str | None = Field(default=None, max_length=4000)
    active: bool
    minimum_stock: int | None = Field(default=None, ge=0)

    model_config = {"extra": "forbid"}

    @field_validator("code", "name", "unit")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be empty or whitespace only")
        return value

    @field_validator("minimum_stock", mode="before")
    @classmethod
    def reject_null_minimum_stock(cls, value: int | None) -> int:
        if value is None:
            raise ValueError("must be a non-negative integer")
        return value

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None


class StockMovementCreate(BaseModel):
    quantity: int = Field(gt=0, strict=True)
    note: str | None = None

    model_config = {"extra": "forbid"}


class StockMovement(BaseModel):
    id: int
    item_id: int
    movement_type: StockMovementType
    quantity: int
    occurred_at: datetime
    note: str | None = None

    model_config = {"from_attributes": True}
