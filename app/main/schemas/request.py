"""Request Pydantic 스키마"""

from datetime import date, datetime
from pydantic import BaseModel, Field, field_validator, model_validator
from app.main.models.models import PickupLocationType, RequestStatus


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


class RequestUpdate(BaseModel):
    """수정 가능 필드만 포함 (business_office_id는 수정 불가)"""
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
    def check_total_quantity(self) -> "RequestUpdate":
        total = self.electric_bed_quantity + self.wheelchair_quantity + self.other_small_quantity
        if total < 1:
            raise ValueError("전체 수량 합계가 1 이상이어야 합니다")
        return self


class RequestStatusTransition(BaseModel):
    """상태 전이 요청 (바로 다음 상태만 허용)"""
    target_status: RequestStatus


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


class RequestListOut(BaseModel):
    """목록 조회 응답 (필터된 항목 + 전체 개수)."""
    items: list[RequestOut]
    total: int


class StatisticsOut(BaseModel):
    """통계 집계 응답 (WP-10).

    - total_requests: 필터 적용 대상 건수 (목록 API의 total과 동일)
    - by_business_office: 필터 결과에 실제 존재하는 사업소만 포함
      (키: 사업소 id 문자열, 값: 건수)
    - by_status: 네 상태 키를 항상 포함 (0건이어도 유지)
    - quantities: 품목별 수량 합계 + total
    """
    total_requests: int = 0
    by_business_office: dict[str, int] = {}
    by_status: dict[str, int] = {}
    quantities: dict[str, int] = {}
