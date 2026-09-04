"""WP-07-B 상태전이 API (PATCH /api/requests/{id}/status) 테스트.

- 임시 SQLite(in-memory) + StaticPool 단일 연결 + TestClient + get_db 오버라이드
- BusinessOffice + RequestNoCounter(id=1) 시딩
- 범위: 성공 200 / 건너뛰기·역방향·중복·DELIVERED 이후·미존재 409 /
        StaleDataError → 409 / 기존 POST·PATCH 수정 API 회귀
"""

import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text, select, func
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
    """임시 SQLite 세션 + 사업소/카운터 시딩 (StaticPool로 단일 연결 공유)."""
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
        "pickup_date": "2099-09-01",
        "pickup_location_type": "자택",
        "pickup_address": "서울시 강남구 테헤란로 123",
        "electric_bed_quantity": 1,
        "wheelchair_quantity": 0,
        "other_small_quantity": 2,
    }


def _history_count(db, request_id: int) -> int:
    return db.execute(
        select(func.count(RequestStatusHistory.id)).where(
            RequestStatusHistory.request_id == request_id
        )
    ).scalar_one()


@pytest.fixture
def created_request_id(client):
    """RECEIVED 상태 접수 1건 생성 후 id 반환."""
    r = client.post("/api/requests", json=_create_payload())
    assert r.status_code == 201, r.text
    return r.json()["id"]


class TestStatusTransitionSuccess:
    """정상 전이 (바로 다음 상태) → 200"""

    def test_received_to_picked_up_200(self, client, test_db, created_request_id):
        r = client.patch(
            f"/api/requests/{created_request_id}/status",
            json={"target_status": "PICKED_UP"},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["id"] == created_request_id
        assert body["current_status"] == "PICKED_UP"
        assert body["completion_date"] is None

        # DB 영속 검증 + 이력 2건 (RECEIVED seq1 + PICKED_UP seq2)
        test_db.expire_all()
        req = test_db.get(Request, created_request_id)
        assert req.current_status == RequestStatus.PICKED_UP
        assert _history_count(test_db, created_request_id) == 2


class TestStatusTransitionSkip:
    """건너뛰기 전이 (RECEIVED → DISINFECTED) → 409, 상태/이력 불변"""

    def test_skip_returns_409(self, client, test_db, created_request_id):
        before = _history_count(test_db, created_request_id)  # 1
        r = client.patch(
            f"/api/requests/{created_request_id}/status",
            json={"target_status": "DISINFECTED"},
        )
        assert r.status_code == 409, r.text
        assert "허용되지 않은 상태 전이" in r.json()["detail"]

        test_db.expire_all()
        req = test_db.get(Request, created_request_id)
        assert req.current_status == RequestStatus.RECEIVED
        assert _history_count(test_db, created_request_id) == before


class TestStatusTransitionReverse:
    """역방향 전이 (PICKED_UP → RECEIVED) → 409, 불변"""

    def test_reverse_returns_409(self, client, test_db, created_request_id):
        # 먼저 PICKED_UP으로 정상 전이
        r = client.patch(
            f"/api/requests/{created_request_id}/status",
            json={"target_status": "PICKED_UP"},
        )
        assert r.status_code == 200, r.text

        before = _history_count(test_db, created_request_id)  # 2
        r2 = client.patch(
            f"/api/requests/{created_request_id}/status",
            json={"target_status": "RECEIVED"},
        )
        assert r2.status_code == 409, r2.text

        test_db.expire_all()
        req = test_db.get(Request, created_request_id)
        assert req.current_status == RequestStatus.PICKED_UP
        assert _history_count(test_db, created_request_id) == before


class TestStatusTransitionDuplicate:
    """동일 상태 중복 전이 (RECEIVED → RECEIVED) → 409 + 이력 개수 불변"""

    def test_same_status_duplicate_409(self, client, test_db, created_request_id):
        before = _history_count(test_db, created_request_id)  # 1
        r = client.patch(
            f"/api/requests/{created_request_id}/status",
            json={"target_status": "RECEIVED"},
        )
        assert r.status_code == 409, r.text
        assert "허용되지 않은 상태 전이" in r.json()["detail"]

        test_db.expire_all()
        assert _history_count(test_db, created_request_id) == before


class TestStatusTransitionAfterDelivered:
    """DELIVERED 이후 전이 → 409, completion_date 유지, 이력 불변"""

    def test_after_delivered_returns_409(self, client, test_db, created_request_id):
        for target in ("PICKED_UP", "DISINFECTED", "DELIVERED"):
            r = client.patch(
                f"/api/requests/{created_request_id}/status",
                json={"target_status": target},
            )
            assert r.status_code == 200, r.text

        before = _history_count(test_db, created_request_id)  # 4
        r = client.patch(
            f"/api/requests/{created_request_id}/status",
            json={"target_status": "DISINFECTED"},
        )
        assert r.status_code == 409, r.text

        test_db.expire_all()
        req = test_db.get(Request, created_request_id)
        assert req.current_status == RequestStatus.DELIVERED
        assert req.completion_date is not None
        assert _history_count(test_db, created_request_id) == before


class TestStatusTransitionNotFound:
    """존재하지 않는 request id → 409"""

    def test_missing_id_returns_409(self, client):
        r = client.patch(
            "/api/requests/99999/status",
            json={"target_status": "PICKED_UP"},
        )
        assert r.status_code == 409, r.text
        assert "존재하지 않는 접수" in r.json()["detail"]


class TestStaleDataError:
    """동시 수정 충돌(StaleDataError) → API 409 재시도 안내"""

    def test_stale_data_error_returns_409(self, client, test_db, created_request_id):
        # 인스턴스를 세션에 로드 (ORM 기준 version=1)
        req = test_db.get(Request, created_request_id)
        assert req is not None

        # 동시 커밋 시뮬레이션: version을 SQL로만 증분 (ORM 세션은 version=1 그대로)
        test_db.execute(
            text("UPDATE requests SET version = version + 1 WHERE id = :id"),
            {"id": created_request_id},
        )
        test_db.commit()

        # 전이 시도 → commit 시 옵티미스트 락 체크 실패 → StaleDataError → 409
        r = client.patch(
            f"/api/requests/{created_request_id}/status",
            json={"target_status": "PICKED_UP"},
        )
        assert r.status_code == 409, r.text
        assert "다시 조회 후 재시도" in r.json()["detail"]

        # 상태/이력은 변경되지 않음
        test_db.expire_all()
        req2 = test_db.get(Request, created_request_id)
        assert req2.current_status == RequestStatus.RECEIVED
        assert _history_count(test_db, created_request_id) == 1


class TestExistingApisRegression:
    """기존 POST 생성 / PATCH 수정 API 회귀"""

    def test_post_create_still_works(self, client):
        r = client.post("/api/requests", json=_create_payload())
        assert r.status_code == 201, r.text
        assert r.json()["current_status"] == "RECEIVED"

    def test_patch_update_still_works(self, client, created_request_id):
        payload = {
            "pickup_date": "2026-09-10",
            "pickup_location_type": "사업소",
            "pickup_address": "부산시 해운대구 센텀중앙로 456",
            "electric_bed_quantity": 2,
            "wheelchair_quantity": 1,
            "other_small_quantity": 3,
        }
        r = client.patch(f"/api/requests/{created_request_id}", json=payload)
        assert r.status_code == 200, r.text
        assert r.json()["pickup_address"] == "부산시 해운대구 센텀중앙로 456"

    def test_patch_update_forbidden_after_transition(self, client, created_request_id):
        # PICKED_UP 전이 후에는 기존처럼 PATCH 수정이 409
        r = client.patch(
            f"/api/requests/{created_request_id}/status",
            json={"target_status": "PICKED_UP"},
        )
        assert r.status_code == 200, r.text

        payload = {
            "pickup_date": "2026-09-15",
            "pickup_location_type": "자택",
            "pickup_address": "서울시 강남구 테헤란로 123",
            "electric_bed_quantity": 1,
            "wheelchair_quantity": 0,
            "other_small_quantity": 2,
        }
        r2 = client.patch(f"/api/requests/{created_request_id}", json=payload)
        assert r2.status_code == 409, r2.text
