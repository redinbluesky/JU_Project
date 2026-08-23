"""WP-07-A 상태 전이 도메인 서비스(transition_request_status) 테스트.

- 임시 SQLite(in-memory) + StaticPool 단일 연결
- RequestNoCounter(id=1) 시딩 (create_request 채번에 필요)
- API 라우터는 이번 청크에 없음 → 서비스 함수를 직접 호출
- 승인된 전이: RECEIVED -> PICKED_UP -> DISINFECTED -> DELIVERED
"""

import pytest
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy import pool

from app.main.db.base import Base
from app.main.models.models import (
    BusinessOffice,
    Request,
    RequestNoCounter,
    RequestStatus,
    RequestStatusHistory,
)
from app.main.schemas.request import RequestCreate
from app.main.services.request_service import create_request, transition_request_status


@pytest.fixture
def db():
    """임시 SQLite DB + 사업소/카운터 시딩"""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=pool.StaticPool,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autocommit=False, expire_on_commit=False)
    session = SessionLocal()

    now = datetime.now(timezone.utc)
    session.add(BusinessOffice(code="OFFICE_A", name="서울사업소", created_at=now))
    session.add(RequestNoCounter(id=1, current_value=0))
    session.commit()

    yield session

    session.close()
    engine.dispose()


@pytest.fixture
def request_id(db) -> int:
    """RECEIVED 상태 접수를 1건 생성하고 id 반환"""
    req = create_request(
        db,
        RequestCreate(
            business_office_id=1,
            pickup_date=date.today() + timedelta(days=7),
            pickup_location_type="자택",
            pickup_address="서울시 강남구 테헤란로 123",
            electric_bed_quantity=1,
            wheelchair_quantity=0,
            other_small_quantity=2,
        ),
    )
    return req.id


def _history(db, rid: int):
    """request_id의 상태 이력을 sequence 오름차순으로 반환"""
    return (
        db.execute(
            select(RequestStatusHistory)
            .where(RequestStatusHistory.request_id == rid)
            .order_by(RequestStatusHistory.sequence)
        )
        .scalars()
        .all()
    )


class TestAllowedTransitions:
    """승인된 전이 성공 시나리오"""

    def test_received_to_picked_up(self, db, request_id):
        req = transition_request_status(db, request_id, RequestStatus.PICKED_UP)

        db.expire_all()
        req = db.get(Request, request_id)
        assert req.current_status == RequestStatus.PICKED_UP
        histories = _history(db, request_id)
        assert [h.sequence for h in histories] == [1, 2]
        assert histories[0].status == RequestStatus.RECEIVED
        assert histories[1].status == RequestStatus.PICKED_UP

    def test_picked_up_to_disinfected(self, db, request_id):
        transition_request_status(db, request_id, RequestStatus.PICKED_UP)
        transition_request_status(db, request_id, RequestStatus.DISINFECTED)

        db.expire_all()
        req = db.get(Request, request_id)
        assert req.current_status == RequestStatus.DISINFECTED
        histories = _history(db, request_id)
        assert [h.sequence for h in histories] == [1, 2, 3]
        assert histories[2].status == RequestStatus.DISINFECTED

    def test_disinfected_to_delivered_records_completion_date(self, db, request_id):
        transition_request_status(db, request_id, RequestStatus.PICKED_UP)
        transition_request_status(db, request_id, RequestStatus.DISINFECTED)
        transition_request_status(db, request_id, RequestStatus.DELIVERED)

        db.expire_all()
        req = db.get(Request, request_id)
        assert req.current_status == RequestStatus.DELIVERED
        assert req.completion_date == datetime.now(timezone.utc).date()
        histories = _history(db, request_id)
        assert [h.sequence for h in histories] == [1, 2, 3, 4]
        assert histories[3].status == RequestStatus.DELIVERED


class TestRejectedTransitions:
    """불법 전이 거부 시나리오 (상태·이력 불변)"""

    def test_skip_disinfected_from_received(self, db, request_id):
        """RECEIVED -> DISINFECTED 건너뛰기 거부"""
        with pytest.raises(ValueError):
            transition_request_status(db, request_id, RequestStatus.DISINFECTED)
        db.rollback()

        db.expire_all()
        req = db.get(Request, request_id)
        assert req.current_status == RequestStatus.RECEIVED
        histories = _history(db, request_id)
        assert [h.sequence for h in histories] == [1]
        assert histories[0].status == RequestStatus.RECEIVED

    def test_backward_picked_up_to_received(self, db, request_id):
        """PICKED_UP -> RECEIVED 역방향 거부"""
        transition_request_status(db, request_id, RequestStatus.PICKED_UP)

        with pytest.raises(ValueError):
            transition_request_status(db, request_id, RequestStatus.RECEIVED)
        db.rollback()

        db.expire_all()
        req = db.get(Request, request_id)
        assert req.current_status == RequestStatus.PICKED_UP
        histories = _history(db, request_id)
        assert [h.sequence for h in histories] == [1, 2]
        assert [h.status for h in histories] == [RequestStatus.RECEIVED, RequestStatus.PICKED_UP]

    def test_same_status_duplicate_rejected(self, db, request_id):
        """RECEIVED -> RECEIVED 중복 거부"""
        with pytest.raises(ValueError):
            transition_request_status(db, request_id, RequestStatus.RECEIVED)
        db.rollback()

        db.expire_all()
        req = db.get(Request, request_id)
        assert req.current_status == RequestStatus.RECEIVED
        histories = _history(db, request_id)
        assert [h.sequence for h in histories] == [1]

    def test_after_delivered_rejected(self, db, request_id):
        """DELIVERED 이후 전이 거부"""
        transition_request_status(db, request_id, RequestStatus.PICKED_UP)
        transition_request_status(db, request_id, RequestStatus.DISINFECTED)
        transition_request_status(db, request_id, RequestStatus.DELIVERED)

        with pytest.raises(ValueError):
            transition_request_status(db, request_id, RequestStatus.DISINFECTED)
        db.rollback()

        db.expire_all()
        req = db.get(Request, request_id)
        assert req.current_status == RequestStatus.DELIVERED
        assert req.completion_date is not None
        histories = _history(db, request_id)
        assert [h.sequence for h in histories] == [1, 2, 3, 4]

    def test_nonexistent_request_id_rejected(self, db):
        """존재하지 않는 id 거부"""
        with pytest.raises(ValueError, match="존재하지 않는"):
            transition_request_status(db, 99999, RequestStatus.PICKED_UP)
