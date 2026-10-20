"""add item stock fields

Revision ID: e8c4da219b07
Revises: a31f7cc984d2
Create Date: 2026-10-20 10:04:52.947495

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e8c4da219b07'
down_revision: Union[str, Sequence[str], None] = 'a31f7cc984d2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "items",
        sa.Column(
            "quantity_available",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
    )
    op.add_column(
        "items",
        sa.Column(
            "minimum_stock",
            sa.Integer(),
            server_default=sa.text("1"),
            nullable=False,
        ),
    )
    op.create_check_constraint(
        "ck_items_quantity_available_nonnegative",
        "items",
        "quantity_available >= 0",
    )
    op.create_check_constraint(
        "ck_items_minimum_stock_nonnegative",
        "items",
        "minimum_stock >= 0",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(
        "ck_items_minimum_stock_nonnegative",
        "items",
        type_="check",
    )
    op.drop_constraint(
        "ck_items_quantity_available_nonnegative",
        "items",
        type_="check",
    )
    op.drop_column("items", "minimum_stock")
    op.drop_column("items", "quantity_available")
