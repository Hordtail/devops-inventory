from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ServerDB(Base):
    __tablename__ = "servers"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
    )

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    ip: Mapped[str] = mapped_column(
        String(45),
        nullable=False,
    )

    environment: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="running",
    )

    location: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )


class ItemDB(Base):
    __tablename__ = "items"
    __table_args__ = (
        CheckConstraint(
            "quantity_available >= 0",
            name="ck_items_quantity_available_nonnegative",
        ),
        CheckConstraint(
            "minimum_stock >= 0",
            name="ck_items_minimum_stock_nonnegative",
        ),
    )

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
    )

    code: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        unique=True,
    )

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    unit: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    image_path: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    quantity_available: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
    )

    minimum_stock: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        server_default=text("1"),
    )

    active: Mapped[bool] = mapped_column(
        nullable=False,
        default=True,
    )


class StockMovementDB(Base):
    __tablename__ = "stock_movements"
    __table_args__ = (
        CheckConstraint(
            "movement_type IN ('IN', 'OUT')",
            name="ck_stock_movements_type_valid",
        ),
        CheckConstraint(
            "quantity > 0",
            name="ck_stock_movements_quantity_positive",
        ),
    )

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
    )

    item_id: Mapped[int] = mapped_column(
        ForeignKey("items.id", ondelete="RESTRICT"),
        nullable=False,
    )

    movement_type: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
    )

    quantity: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    note: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
