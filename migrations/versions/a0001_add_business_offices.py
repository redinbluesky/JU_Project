"""add business_offices table and seed initial data

Revision ID: a0001
Revises: 
Create Date: 2026-08-23 00:00:00.000000

"""
from datetime import datetime
from typing import TYPE_CHECKING

from alembic import op
import sqlalchemy as sa

if TYPE_CHECKING:
    from app.main.db.base import UTCDateTime


revision = "a0001"
down_revision = None
depends_on = None


def upgrade():
    op.create_table(
        "business_offices",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("code", sa.String(50), nullable=False, unique=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    initial_data = [
        {
            "id": 1,
            "code": "OFFICE_A",
            "name": "서울사업소",
            "created_at": datetime(2026, 1, 1, 0, 0, 0),
        },
        {
            "id": 2,
            "code": "OFFICE_B",
            "name": "부산사업소",
            "created_at": datetime(2026, 1, 1, 0, 0, 0),
        },
        {
            "id": 3,
            "code": "OFFICE_C",
            "name": "제주사업소",
            "created_at": datetime(2026, 1, 1, 0, 0, 0),
        },
    ]

    for row in initial_data:
        op.execute(
            f"INSERT INTO business_offices (id, code, name, created_at) "
            f"VALUES ({row['id']}, '{row['code']}', '{row['name']}', "
            f"'{row['created_at'].strftime('%Y-%m-%d %H:%M:%S')}')"
        )


def downgrade():
    op.drop_table("business_offices")
