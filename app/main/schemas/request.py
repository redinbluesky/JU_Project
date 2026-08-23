"""Request Pydantic 스키마"""

from datetime import date, datetime
from pydantic import BaseModel, Field, field_validator, model_validator
from app.main.models.models import PickupLocationType


class RequestCreate(BaseModel):
    business_office_id: int = Field(..., gt=0)
    pickup_date: date
    pickup_location_type: PickupLocationType
    pickup_address: str = Field(..., min_length=1, max_length=255)
    electric_bed_quantity: int = Field(..., ge=0)
    wheelchair_quantity: int = Field(..., ge=0)
    other_small_quantity: int = Field(..., ge=0)

    @field_validator("pickup_date")
    @classmethod
    def pickup_date_not_in_past(cls, v: date) -> date:
        """pickup_date는 오늘 이전 날짜는 거부 (오늘 포함 과거 거부)"""
        today = date.today()
        if v <= today:
            raise ValueError("pickup_date는 오늘 이전 날짜일 수 없습니다")
        return v

    @model_validator(mode="after")
    def check_total_quantity(self) -> "RequestCreate":
        total = self.electric_bed_quantity + self.wheelchair_quantity + self.other_small_quantity
        if total < 1:
            raise ValueError("전체 수량 합계가 1 이상이어야 합니다")
        return self


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
