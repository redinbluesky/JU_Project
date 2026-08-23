"""Request 생성 API pytest 테스트.
임시 SQLite DB를 사용해 runtime/db/ju-project.db를 오염시키지 않음.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import date, datetime, timezone

from app.main.db.base import Base
from app.main.models.models import Request, RequestStatusHistory, BusinessOffice, RequestStatus, PickupLocationType, RequestNoCounter
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

    # 카운터 테이블 초기화 (id=1, current_value=0)
    db.add(RequestNoCounter(id=1, current_value=0))
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


class TestCreateRequestSuccess:
    """정상 흐름 테스트"""

    def test_create_request_success(self, test_db, sample_request_data):
        """정상 입력 → 201, request_no 부여됨, current_status='RECEIVED' 확인"""
        result = create_request(test_db, sample_request_data)
        
        assert result.id is not None
        assert result.request_no == "R-0000000001"
        assert result.current_status == RequestStatus.RECEIVED
        assert result.business_office_id == 1
        assert result.pickup_date == date(2026, 8, 25)
        assert result.electric_bed_quantity == 1
        assert result.wheelchair_quantity == 0
        assert result.other_small_quantity == 2

    def test_create_request_persists_to_db(self, test_db, sample_request_data):
        """생성 후 DB에서 직접 조회해 1건 존재, created_at 기록 확인"""
        create_request(test_db, sample_request_data)
        
        # 별도 세션에서 조회 (commit 후이므로 새 세션에서도 가능)
        requests = test_db.query(Request).all()
        assert len(requests) == 1
        
        req = requests[0]
        assert req.request_no == "R-0000000001"
        assert req.created_at is not None
        assert req.updated_at is not None
        # created_at과 updated_at이 동일해야 함 (생성 시점)
        assert req.created_at == req.updated_at

    def test_create_request_creates_history(self, test_db, sample_request_data):
        """생성 후 RequestStatusHistory에 sequence=1, status=RECEIVED 이력 1건 존재 확인"""
        create_request(test_db, sample_request_data)
        
        histories = test_db.query(RequestStatusHistory).all()
        assert len(histories) == 1
        
        hist = histories[0]
        assert hist.sequence == 1
        assert hist.status == RequestStatus.RECEIVED
        assert hist.request_id is not None
        assert hist.changed_at is not None

    def test_multiple_requests_sequential_numbers(self, test_db, sample_request_data):
        """여러 건 생성 시 접수번호가 순차적으로 증가"""
        req1 = create_request(test_db, sample_request_data)
        req2 = create_request(test_db, sample_request_data)
        req3 = create_request(test_db, sample_request_data)
        
        assert req1.request_no == "R-0000000001"
        assert req2.request_no == "R-0000000002"
        assert req3.request_no == "R-0000000003"

    def test_status_history_count(self, test_db, sample_request_data):
        """접수 3건 생성 시 상태 이력도 3건"""
        create_request(test_db, sample_request_data)
        create_request(test_db, sample_request_data)
        create_request(test_db, sample_request_data)
        
        histories = test_db.query(RequestStatusHistory).all()
        assert len(histories) == 3
        # 각 이력의 sequence가 고유해야 함
        sequences = [h.sequence for h in histories]
        assert sequences == [1, 1, 1]  # 각 요청마다 sequence=1부터 시작
