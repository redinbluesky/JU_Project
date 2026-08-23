"""WP-12-A 핵심 업무 흐름 통합 테스트.

접수 생성 → 수정 → 상태 전이(PICKED_UP → DISINFECTED → DELIVERED)
→ 잘못된 입력 422(저장 안 됨)를 실제 FastAPI 라우터로 검증한다.

- 임시 SQLite(in-memory) + StaticPool 단일 연결 + TestClient
- get_db 의존성 오버라이드로 앱 코드 미수정
- 하나의 테스트에서 지시서 8개 항목을 순서대로 검증
"""

import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import sessionmaker
from sqlalchemy import pool

from app.main.db.base import Base
from app.main.models.models import (
    Request,
    BusinessOffice,
    RequestStatus,
    RequestStatusHistory,
    RequestNoCounter,
)
from app.main.api.requests import get_db
from app.server import app


@pytest.fixture
def test_db():
    """임시 SQLite 세션 + BusinessOffice/RequestNoCounter 시딩 (StaticPool 단일 연결 공유)."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=pool.StaticPool,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autocommit=False, expire_on_commit=False)
    db = SessionLocal()

    now = datetime.now(timezone.utc)
    db.add(BusinessOffice(code="OFFICE_A", name="서울사업소", created_at=now))
    db.commit()
    db.add(RequestNoCounter(id=1, current_value=0))
    db.commit()

    yield db
    db.close()
    engine.dispose()


@pytest.fixture
def client(test_db):
    """get_db를 임시 세션으로 오버라이드한 TestClient."""

    def override_get_db():
        yield test_db

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.pop(get_db, None)


def _create_payload() -> dict:
    return {
        "business_office_id": 1,
        "pickup_date": "2026-09-01",
        "pickup_location_type": "자택",
        "pickup_address": "서울시 강남구 테헤란로 123",
        "electric_bed_quantity": 1,
        "wheelchair_quantity": 0,
        "other_small_quantity": 2,
    }


def _request_count(db) -> int:
    return db.execute(select(func.count(Request.id))).scalar_one()


def _history(db, request_id: int) -> list[tuple[int, str]]:
    """[(sequence, status_value), ...]를 sequence 정렬로 반환."""
    rows = db.execute(
        select(RequestStatusHistory.sequence, RequestStatusHistory.status)
        .where(RequestStatusHistory.request_id == request_id)
        .order_by(RequestStatusHistory.sequence)
    ).all()
    return [(seq, status.value) for seq, status in rows]


class TestCoreBusinessFlow:
    """핵심 업무 흐름: 생성 → 수정 → 상태 3단계 전이 → 배송완료 + 오류 입력 422."""

    def test_full_flow_and_invalid_input(self, client, test_db):
        # --- 1. 시딩 확인: BusinessOffice + RequestNoCounter ---
        office = test_db.get(BusinessOffice, 1)
        assert office is not None
        assert office.name == "서울사업소"
        counter = test_db.get(RequestNoCounter, 1)
        assert counter is not None
        assert counter.current_value == 0

        # --- 2. 접수 생성 → 201, RECEIVED ---
        r = client.post("/api/requests", json=_create_payload())
        assert r.status_code == 201, r.text
        body = r.json()
        req_id = body["id"]
        assert body["request_no"] == "R-0000000001"
        assert body["current_status"] == "RECEIVED"
        assert body["completion_date"] is None
        assert _request_count(test_db) == 1

        # --- 3. PATCH 수정 → 200, 주소/수량 변경 ---
        r = client.patch(
            f"/api/requests/{req_id}",
            json={
                "pickup_date": "2026-09-02",
                "pickup_location_type": "사업소",
                "pickup_address": "서울시 강남구 테헤란로 456",
                "electric_bed_quantity": 2,
                "wheelchair_quantity": 1,
                "other_small_quantity": 0,
            },
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["pickup_date"] == "2026-09-02"
        assert body["pickup_address"] == "서울시 강남구 테헤란로 456"
        assert (body["electric_bed_quantity"], body["wheelchair_quantity"], body["other_small_quantity"]) == (2, 1, 0)

        # DB 영속 확인
        test_db.expire_all()
        req = test_db.get(Request, req_id)
        assert req.pickup_address == "서울시 강남구 테헤란로 456"
        assert (req.electric_bed_quantity, req.wheelchair_quantity, req.other_small_quantity) == (2, 1, 0)
        assert req.current_status == RequestStatus.RECEIVED

        # --- 4. RECEIVED → PICKED_UP → 200 ---
        r = client.patch(f"/api/requests/{req_id}/status", json={"target_status": "PICKED_UP"})
        assert r.status_code == 200, r.text
        assert r.json()["current_status"] == "PICKED_UP"
        assert r.json()["completion_date"] is None

        # --- 5. PICKED_UP → DISINFECTED → 200 ---
        r = client.patch(f"/api/requests/{req_id}/status", json={"target_status": "DISINFECTED"})
        assert r.status_code == 200, r.text
        assert r.json()["current_status"] == "DISINFECTED"
        assert r.json()["completion_date"] is None

        # --- 6. DISINFECTED → DELIVERED → 200, completion_date not null ---
        r = client.patch(f"/api/requests/{req_id}/status", json={"target_status": "DELIVERED"})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["current_status"] == "DELIVERED"
        assert body["completion_date"] is not None

        # --- 7. DB 최종 상태: DELIVERED, 이력 4건, sequence [1,2,3,4] ---
        test_db.expire_all()
        req = test_db.get(Request, req_id)
        assert req.current_status == RequestStatus.DELIVERED
        assert req.completion_date is not None
        assert _request_count(test_db) == 1

        hist = _history(test_db, req_id)
        assert [seq for seq, _ in hist] == [1, 2, 3, 4]
        assert [st for _, st in hist] == ["RECEIVED", "PICKED_UP", "DISINFECTED", "DELIVERED"]

        # --- 8. 잘못된 입력(전체 수량 0) → 422, Request 수 증가 없음 ---
        bad = _create_payload()
        bad["electric_bed_quantity"] = 0
        bad["wheelchair_quantity"] = 0
        bad["other_small_quantity"] = 0
        r = client.post("/api/requests", json=bad)
        assert r.status_code == 422, r.text
        assert _request_count(test_db) == 1
        test_db.expire_all()
        assert test_db.get(RequestNoCounter, 1).current_value == 1
