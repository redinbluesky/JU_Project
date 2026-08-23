"""Request Pydantic 스키마"""

from datetime import date, datetime
from pydantic import BaseModel, Field
from app.main.models.models import PickupLocationType


class RequestCreate(BaseModel):
    business_office_id: int = Field(..., gt=0)
    pickup_date: date
    pickup_location_type: PickupLocationType
    pickup_address: str = Field(..., min_length=1, max_length=255)
    electric_bed_quantity: int = Field(..., ge=0)
    wheelchair_quantity: int = Field(..., ge=0)
    other_small_quantity: int = Field(..., ge=0)


class RequestOut(BaseModel):
    id: int
    request_no: str
    business_office_id: int
    pickup_date: date
    pickup_location_type: str
    pickup_address: str
    current_status: str
    electric_bed_quantity: int
    wheelchair_quantity: int
    other_small_quantity: int
    completion_date: date | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
