"""Request 생성 API 오류 검증 pytest.
5가지 오류 케이스 각각 최소 1개 + 정상 케이스 회귀 확인.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import date, datetime, timezone
from pydantic import ValidationError

from app.main.db.base import Base
from app.main.models.models import Request, RequestStatusHistory, BusinessOffice, RequestStatus, PickupLocationType
from app.main.schemas.request import RequestCreate
from app.main.services.request_service import create_request


@pytest.fixture
def test_db():
    """임시 SQLite DB 세션 생성"""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autocommit=False, expire_on_commit=False)
    db = SessionLocal()
    
    # 초기 사업소 데이터 삽입
    now = datetime.now(timezone.utc)
    db.add(BusinessOffice(code="OFFICE_A", name="서울사업소", created_at=now))
    db.add(BusinessOffice(code="OFFICE_B", name="부산사업소", created_at=now))
    db.add(BusinessOffice(code="OFFICE_C", name="제주사업소", created_at=now))
    db.commit()
    
    yield db
    
    db.close()


@pytest.fixture
def sample_request_data():
    """정상 입력 데이터"""
    return RequestCreate(
        business_office_id=1,
        pickup_date=date(2026, 8, 25),
        pickup_location_type=PickupLocationType.HOME,
        pickup_address="서울시 강남구 테헤란로 123",
        electric_bed_quantity=1,
        wheelchair_quantity=0,
        other_small_quantity=2,
    )


class TestRejectAllQuantitiesZero:
    """QA-005: 모든 품목 수량 0 → 거부"""

    def test_reject_all_zero(self, test_db):
        """전체 수량 0 → Pydantic ValidationError 발생, DB에 저장 안 됨"""
        with pytest.raises(ValidationError):
            RequestCreate(
                business_office_id=1,
                pickup_date=date(2026, 8, 25),
                pickup_location_type=PickupLocationType.HOME,
                pickup_address="서울시 강남구 테헤란로 123",
                electric_bed_quantity=0,
                wheelchair_quantity=0,
                other_small_quantity=0,
            )
        
        # DB에 저장 안 됨
        assert test_db.query(Request).count() == 0


class TestRejectNegativeQuantity:
    """QA-006: 음수 수량 → 거부"""

    def test_reject_negative_electric_bed(self, test_db):
        """전동침대 음수 → Pydantic ValidationError 발생"""
        with pytest.raises(ValidationError):
            RequestCreate(
                business_office_id=1,
                pickup_date=date(2026, 8, 25),
                pickup_location_type=PickupLocationType.HOME,
                pickup_address="서울시 강남구 테헤란로 123",
                electric_bed_quantity=-1,
                wheelchair_quantity=0,
                other_small_quantity=0,
            )
        
        assert test_db.query(Request).count() == 0

    def test_reject_negative_wheelchair(self, test_db):
        """휠체어 음수 → Pydantic ValidationError 발생"""
        with pytest.raises(ValidationError):
            RequestCreate(
                business_office_id=1,
                pickup_date=date(2026, 8, 25),
                pickup_location_type=PickupLocationType.HOME,
                pickup_address="서울시 강남구 테헤란로 123",
                electric_bed_quantity=1,
                wheelchair_quantity=-1,
                other_small_quantity=0,
            )
        
        assert test_db.query(Request).count() == 0


class TestRejectNonIntegerQuantity:
    """QA-007: 정수가 아닌 수량 → 거부"""

    def test_reject_decimal_quantity(self, test_db):
        """소수점 수량 → Pydantic ValidationError 발생"""
        with pytest.raises(ValidationError):
            RequestCreate(
                business_office_id=1,
                pickup_date=date(2026, 8, 25),
                pickup_location_type=PickupLocationType.HOME,
                pickup_address="서울시 강남구 테헤란로 123",
                electric_bed_quantity=1.5,
                wheelchair_quantity=0,
                other_small_quantity=0,
            )
        
        assert test_db.query(Request).count() == 0

    def test_reject_string_quantity(self, test_db):
        """문자열 수량 → Pydantic ValidationError 발생"""
        with pytest.raises(ValidationError):
            RequestCreate(
                business_office_id=1,
                pickup_date=date(2026, 8, 25),
                pickup_location_type=PickupLocationType.HOME,
                pickup_address="서울시 강남구 테헤란로 123",
                electric_bed_quantity="abc",
                wheelchair_quantity=0,
                other_small_quantity=0,
            )
        
        assert test_db.query(Request).count() == 0


class TestRejectPastDate:
    """QA-008: 오늘 이전 날짜 → 거부"""

    def test_reject_yesterday(self, test_db):
        """어제 날짜 → Pydantic ValidationError 발생"""
        yesterday = date.today() - __import__('datetime').timedelta(days=1)
        with pytest.raises(ValidationError):
            RequestCreate(
                business_office_id=1,
                pickup_date=yesterday,
                pickup_location_type=PickupLocationType.HOME,
                pickup_address="서울시 강남구 테헤란로 123",
                electric_bed_quantity=1,
                wheelchair_quantity=0,
                other_small_quantity=0,
            )
        
        assert test_db.query(Request).count() == 0

    def test_reject_today(self, test_db):
        """오늘 날짜 → Pydantic ValidationError 발생"""
        today = date.today()
        with pytest.raises(ValidationError):
            RequestCreate(
                business_office_id=1,
                pickup_date=today,
                pickup_location_type=PickupLocationType.HOME,
                pickup_address="서울시 강남구 테헤란로 123",
                electric_bed_quantity=1,
                wheelchair_quantity=0,
                other_small_quantity=0,
            )
        
        assert test_db.query(Request).count() == 0


class TestRejectMissingRequiredField:
    """QA-009: 필수값 누락 → 거부"""

    def test_reject_missing_business_office_id(self, test_db):
        """business_office_id 누락 → Pydantic ValidationError 발생"""
        with pytest.raises(ValidationError):
            RequestCreate(
                pickup_date=date(2026, 8, 25),
                pickup_location_type=PickupLocationType.HOME,
                pickup_address="서울시 강남구 테헤란로 123",
                electric_bed_quantity=1,
                wheelchair_quantity=0,
                other_small_quantity=0,
            )
        
        assert test_db.query(Request).count() == 0

    def test_reject_missing_pickup_date(self, test_db):
        """pickup_date 누락 → Pydantic ValidationError 발생"""
        with pytest.raises(ValidationError):
            RequestCreate(
                business_office_id=1,
                pickup_location_type=PickupLocationType.HOME,
                pickup_address="서울시 강남구 테헤란로 123",
                electric_bed_quantity=1,
                wheelchair_quantity=0,
                other_small_quantity=0,
            )
        
        assert test_db.query(Request).count() == 0

    def test_reject_missing_pickup_address(self, test_db):
        """pickup_address 누락 → Pydantic ValidationError 발생"""
        with pytest.raises(ValidationError):
            RequestCreate(
                business_office_id=1,
                pickup_date=date(2026, 8, 25),
                pickup_location_type=PickupLocationType.HOME,
                electric_bed_quantity=1,
                wheelchair_quantity=0,
                other_small_quantity=0,
            )
        
        assert test_db.query(Request).count() == 0


class TestRegression:
    """정상 케이스 회귀 확인"""

    def test_normal_still_works(self, test_db, sample_request_data):
        """정상 입력 → 여전히 성공해야 함"""
        result = create_request(test_db, sample_request_data)
        
        assert result.id is not None
        assert result.request_no == "R-0000000001"
        assert result.current_status == RequestStatus.RECEIVED
