from sqlalchemy import String
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