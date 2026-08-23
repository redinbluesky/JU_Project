"""add requests table and request_no_counter table

Revision ID: a0002
Revises: a0001
Create Date: 2026-08-23 00:00:00.000000

"""
from typing import TYPE_CHECKING

from alembic import op
import sqlalchemy as sa

if TYPE_CHECKING:
    from app.main.db.base import UTCDateTime


revision = "a0002"
down_revision = "a0001"
depends_on = None


def upgrade():
    # requests 테이블 생성
    op.create_table(
        "requests",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("request_no", sa.String(30), nullable=False, unique=True),
        sa.Column("business_office_id", sa.Integer, sa.ForeignKey("business_offices.id"), nullable=False),
        sa.Column("pickup_date", sa.Date, nullable=False),
        sa.Column("pickup_location_type", sa.String(10), nullable=False),
        sa.Column("pickup_address", sa.String(255), nullable=False),
        sa.Column("current_status", sa.String(20), nullable=False),
        sa.Column("electric_bed_quantity", sa.Integer, nullable=False),
        sa.Column("wheelchair_quantity", sa.Integer, nullable=False),
        sa.Column("other_small_quantity", sa.Integer, nullable=False),
        sa.Column("completion_date", sa.Date, nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("version", sa.Integer, nullable=False, default=0),
        sa.CheckConstraint(
            "electric_bed_quantity + wheelchair_quantity + other_small_quantity >= 1",
            name="chk_total_quantity_positive",
        ),
        sa.CheckConstraint(
            "current_status IN ('RECEIVED', 'PICKED_UP', 'DISINFECTED', 'DELIVERED')",
            name="chk_current_status",
        ),
        sa.CheckConstraint(
            "pickup_location_type IN ('사업소', '자택')",
            name="chk_pickup_location_type",
        ),
    )

    # 인덱스 생성
    op.create_index("idx_request_no", "requests", ["request_no"], unique=True)
    op.create_index("idx_business_office_id", "requests", ["business_office_id"])
    op.create_index("idx_current_status", "requests", ["current_status"])
    op.create_index("idx_pickup_date", "requests", ["pickup_date"])
    op.create_index("idx_bo_status", "requests", ["business_office_id", "current_status"])

    # request_no_counter 테이블 생성
    op.create_table(
        "request_no_counter",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("current_value", sa.Integer, nullable=False, default=0),
        sa.CheckConstraint("id = 1", name="chk_counter_id_is_one"),
    )

    # 카운터 초기값 0으로 시딩
    op.execute("INSERT INTO request_no_counter (id, current_value) VALUES (1, 0)")


def downgrade():
    op.drop_table("request_no_counter")
    op.drop_table("requests")
