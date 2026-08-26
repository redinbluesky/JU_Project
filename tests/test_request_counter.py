"""RequestNoCounter 기반 채번 pytest 테스트.
임시 SQLite DB를 사용해 runtime/db/ju-project.db를 오염시키지 않음.
"""

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from datetime import date, datetime, timedelta, timezone

from app.main.db.base import Base
from app.main.models.models import Request, RequestStatusHistory, BusinessOffice, RequestStatus, PickupLocationType, RequestNoCounter
from app.main.schemas.request import RequestCreate
from app.main.services.request_service import create_request

VALID_PICKUP_DATE = date.today() + timedelta(days=1)


@pytest.fixture
def test_db():
    """임시 SQLite DB 세션 생성 + 카운터 초기화 (FK 활성화)"""
    engine = create_engine("sqlite:///:memory:")

    # SQLite에서 Foreign Key 활성화
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys = ON")
        cursor.close()

    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autocommit=False, expire_on_commit=False)
    db = SessionLocal()

    # 초기 사업소 데이터
    now = datetime.now(timezone.utc)
    db.add(BusinessOffice(code="OFFICE_A", name="서울사업소", created_at=now))
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
        pickup_date=VALID_PICKUP_DATE,
        pickup_location_type=PickupLocationType.HOME,
        pickup_address="서울시 강남구 테헤란로 123",
        electric_bed_quantity=1,
        wheelchair_quantity=0,
        other_small_quantity=2,
    )


class TestCounterIncrementsSequentially:
    """3건 연속 생성 시 request_no가 R-0000000001, R-0000000002, R-0000000003으로 정확히 증가"""

    def test_counter_increments_sequentially(self, test_db, sample_request_data):
        req1 = create_request(test_db, sample_request_data)
        req2 = create_request(test_db, sample_request_data)
        req3 = create_request(test_db, sample_request_data)

        assert req1.request_no == "R-0000000001"
        assert req2.request_no == "R-0000000002"
        assert req3.request_no == "R-0000000003"


class TestCounterPersistsInDB:
    """생성 후 request_no_counter.current_value가 실제로 증가했는지 DB 직접 조회"""

    def test_counter_persists_in_db(self, test_db, sample_request_data):
        create_request(test_db, sample_request_data)
        create_request(test_db, sample_request_data)
        create_request(test_db, sample_request_data)

        counter = test_db.query(RequestNoCounter).filter(RequestNoCounter.id == 1).first()
        assert counter is not None
        assert counter.current_value == 3


class TestCounterRollbackOnFailure:
    """생성 실패 시 카운터가 롤백되는지 확인"""

    def test_counter_rollback_on_failure(self, test_db, sample_request_data):
        # 먼저 1건 정상 생성 → R-0000000001
        req1 = create_request(test_db, sample_request_data)
        assert req1.request_no == "R-0000000001"

        # 카운터가 1 증가했는지 확인
        counter = test_db.query(RequestNoCounter).filter(RequestNoCounter.id == 1).first()
        assert counter.current_value == 1

        # FK 위반을 유도: 존재하지 않는 business_office_id(999)로 호출
        bad_data = RequestCreate(
            business_office_id=999,
            pickup_date=VALID_PICKUP_DATE,
            pickup_location_type=PickupLocationType.HOME,
            pickup_address="서울시 강남구 테헤란로 123",
            electric_bed_quantity=1,
            wheelchair_quantity=0,
            other_small_quantity=0,
        )

        # FK 위반으로 인해 예외가 발생
        with pytest.raises(Exception):
            create_request(test_db, bad_data)

        # 예외 후 세션이 broken 상태이므로 직접 rollback
        test_db.rollback()

        # 롤백 확인: 카운터가 증가하지 않았어야 함
        counter_after = test_db.query(RequestNoCounter).filter(RequestNoCounter.id == 1).first()
        assert counter_after.current_value == 1, f"카운터가 롤백되지 않음: {counter_after.current_value}"

        # 다음 정상 생성이 R-0000000002가 되어야 함 (카운터가 1에서 증가)
        req2 = create_request(test_db, sample_request_data)
        assert req2.request_no == "R-0000000002"
