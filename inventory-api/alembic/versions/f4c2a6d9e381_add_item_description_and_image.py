"""add item description and image reference

Revision ID: f4c2a6d9e381
Revises: b7d2e8f41c6a
Create Date: 2026-10-20 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f4c2a6d9e381"
down_revision: Union[str, Sequence[str], None] = "b7d2e8f41c6a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "items",
        sa.Column("description", sa.Text(), nullable=True),
    )
    op.add_column(
        "items",
        sa.Column("image_path", sa.String(length=255), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("items", "image_path")
    op.drop_column("items", "description")
