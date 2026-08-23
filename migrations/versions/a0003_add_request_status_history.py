"""add request_status_history table

Revision ID: a0003
Revises: a0002
Create Date: 2026-08-23 00:00:00.000000

"""
from typing import TYPE_CHECKING

from alembic import op
import sqlalchemy as sa

if TYPE_CHECKING:
    from app.main.db.base import UTCDateTime


revision = "a0003"
down_revision = "a0002"
depends_on = None


def upgrade():
    op.create_table(
        "request_status_history",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("request_id", sa.Integer, sa.ForeignKey("requests.id"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("changed_at", sa.DateTime(), nullable=False),
        sa.Column("sequence", sa.Integer, nullable=False),
        sa.CheckConstraint(
            "status IN ('RECEIVED', 'PICKED_UP', 'DISINFECTED', 'DELIVERED')",
            name="chk_status_in_history",
        ),
        sa.UniqueConstraint("request_id", "sequence", name="uq_request_sequence"),
    )

    op.create_index("idx_request_id", "request_status_history", ["request_id"])
    op.create_index("idx_request_seq", "request_status_history", ["request_id", "sequence"])


def downgrade():
    op.drop_table("request_status_history")
