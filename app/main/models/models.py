import enum
from datetime import date, datetime
from sqlalchemy import (
    Column,
    Integer,
    String,
    Date,
    Enum as SAEnum,
    ForeignKey,
    CheckConstraint,
    UniqueConstraint,
)
from app.main.db.base import Base, UTCDateTime


class RequestStatus(str, enum.Enum):
    RECEIVED = "RECEIVED"
    PICKED_UP = "PICKED_UP"
    DISINFECTED = "DISINFECTED"
    DELIVERED = "DELIVERED"


class PickupLocationType(str, enum.Enum):
    OFFICE = "사업소"
    HOME = "자택"


class BusinessOffice(Base):
    __tablename__ = "business_offices"
    id = Column(Integer, primary_key=True)
    code = Column(String(50), nullable=False, unique=True)
    name = Column(String(100), nullable=False)
    created_at = Column(UTCDateTime(), nullable=False)


class Request(Base):
    __tablename__ = "requests"
    id = Column(Integer, primary_key=True)
    request_no = Column(String(30), nullable=False, unique=True)
    business_office_id = Column(Integer, ForeignKey("business_offices.id"), nullable=False)
    pickup_date = Column(Date, nullable=False)
    pickup_location_type = Column(
        SAEnum(PickupLocationType, native_enum=False, length=10, validate_strings=True, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )
    pickup_address = Column(String(255), nullable=False)
    current_status = Column(
        SAEnum(RequestStatus, native_enum=False, length=20, validate_strings=True),
        nullable=False,
    )
    electric_bed_quantity = Column(Integer, nullable=False)
    wheelchair_quantity = Column(Integer, nullable=False)
    other_small_quantity = Column(Integer, nullable=False)
    completion_date = Column(Date, nullable=True)
    created_at = Column(UTCDateTime(), nullable=False)
    updated_at = Column(UTCDateTime(), nullable=False)
    version = Column(Integer, nullable=False, default=0)

    __mapper_args__ = {
        "version_id_col": version,
        "version_id_generator": lambda current_version: (current_version or 0) + 1,
    }

    __table_args__ = (
        CheckConstraint(
            "electric_bed_quantity + wheelchair_quantity + other_small_quantity >= 1",
            name="chk_total_quantity_positive",
        ),
    )


class RequestStatusHistory(Base):
    __tablename__ = "request_status_history"
    id = Column(Integer, primary_key=True)
    request_id = Column(Integer, ForeignKey("requests.id"), nullable=False)
    status = Column(
        SAEnum(RequestStatus, native_enum=False, length=20, validate_strings=True),
        nullable=False,
    )
    changed_at = Column(UTCDateTime(), nullable=False)
    sequence = Column(Integer, nullable=False)

    __table_args__ = (
        UniqueConstraint("request_id", "sequence", name="uq_request_sequence"),
    )


class RequestNoCounter(Base):
    __tablename__ = "request_no_counter"
    id = Column(Integer, primary_key=True)
    current_value = Column(Integer, nullable=False, default=0)

    __table_args__ = (
        CheckConstraint("id = 1", name="chk_counter_id_is_one"),
    )
