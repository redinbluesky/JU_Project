"""WP-14-A — 500 응답의 내부 예외 원문 노출 방지 검증.

검증 항목:
1. 상태전이·접수 생성·접수 수정 API에서 예상 밖 예외(RuntimeError) 발생 시
   500 응답 detail에 예외 원문·DB 경로가 포함되지 않고 안전한 고정 메시지만 반환.
2. 기존 ValueError 409 동작 유지:
   - 수정 대상 미존재 → 409
   - 상태 전이 불가(건너뛰기/미존재) → 409
   - RECEIVED 이외 상태의 수정 → 409

방식: 임시 SQLite(in-memory) + StaticPool + TestClient,
get_db 의존성 오버라이드. RuntimeError는
app.main.api.requests 모듈 네임스페이스의 서비스 함수를 monkeypatch로 유도한다.
"""

import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, pool
from sqlalchemy.orm import sessionmaker

from app.main.db.base import Base
from app.main.models.models import BusinessOffice, RequestNoCounter
from app.main.api.requests import get_db
from app.server import app

import app.main.api.requests as api_module

CREATE_500_DETAIL = "접수 생성 중 서버 오류가 발생했습니다."
UPDATE_500_DETAIL = "접수 수정 중 서버 오류가 발생했습니다."
TRANSITION_500_DETAIL = "상태 변경 중 서버 오류가 발생했습니다."


@pytest.fixture
def test_db():
    """임시 SQLite 세션 + 시딩 (StaticPool 단일 연결 공유)."""
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
        "pickup_date": "2099-09-01",
        "pickup_location_type": "자택",
        "pickup_address": "서울시 강남구 테헤란로 123",
        "electric_bed_quantity": 1,
        "wheelchair_quantity": 0,
        "other_small_quantity": 2,
    }


def _create_request(client) -> int:
    r = client.post("/api/requests", json=_create_payload())
    assert r.status_code == 201, r.text
    return r.json()["id"]


class TestServerErrorNoLeak:
    """예상 밖 예외 → 500 고정 메시지, 내부 원문 미노출."""

    def test_create_500_no_leak(self, client, monkeypatch):
        """접수 생성 중 RuntimeError → 500 + 고정 메시지 + 원문/경로 미노출."""
        def boom(db, data):
            raise RuntimeError(f"internal-secret marker DB path /tmp/db.sqlite3")

        monkeypatch.setattr(api_module, "create_request", boom)

        r = client.post("/api/requests", json=_create_payload())
        assert r.status_code == 500, r.text
        body = r.json()
        assert body["detail"] == CREATE_500_DETAIL
        text = r.text
        assert "internal-secret marker" not in text
        assert "/tmp/db.sqlite3" not in text
        assert "RuntimeError" not in text

    def test_update_500_no_leak(self, client, monkeypatch):
        """접수 수정 중 RuntimeError → 500 + 고정 메시지 + 원문/경로 미노출."""
        req_id = _create_request(client)

        def boom(db, request_id, data):
            raise RuntimeError(f"internal-secret marker DB path /tmp/db.sqlite3")

        monkeypatch.setattr(api_module, "update_request", boom)

        r = client.patch(
            f"/api/requests/{req_id}",
            json={
                "pickup_date": "2099-09-02",
                "pickup_location_type": "자택",
                "pickup_address": "수정 주소",
                "electric_bed_quantity": 1,
                "wheelchair_quantity": 1,
                "other_small_quantity": 1,
            },
        )
        assert r.status_code == 500, r.text
        body = r.json()
        assert body["detail"] == UPDATE_500_DETAIL
        text = r.text
        assert "internal-secret marker" not in text
        assert "/tmp/db.sqlite3" not in text
        assert "RuntimeError" not in text

    def test_transition_500_no_leak(self, client, monkeypatch):
        """상태 전이 중 RuntimeError → 500 + 고정 메시지 + 원문/경로 미노출."""
        req_id = _create_request(client)

        def boom(db, request_id, target_status):
            raise RuntimeError(f"internal-secret marker DB path /tmp/db.sqlite3")

        monkeypatch.setattr(api_module, "transition_request_status", boom)

        r = client.patch(
            f"/api/requests/{req_id}/status", json={"target_status": "PICKED_UP"}
        )
        assert r.status_code == 500, r.text
        body = r.json()
        assert body["detail"] == TRANSITION_500_DETAIL
        text = r.text
        assert "internal-secret marker" not in text
        assert "/tmp/db.sqlite3" not in text
        assert "RuntimeError" not in text


class TestExistingConflictBehavior:
    """기존 ValueError 409 동작 유지."""

    def test_update_nonexistent_returns_409(self, client):
        r = client.patch(
            "/api/requests/99999",
            json={
                "pickup_date": "2099-09-02",
                "pickup_location_type": "자택",
                "pickup_address": "주소",
                "electric_bed_quantity": 1,
                "wheelchair_quantity": 0,
                "other_small_quantity": 0,
            },
        )
        assert r.status_code == 409, r.text
        assert "존재하지 않는 접수" in r.json()["detail"]

    def test_invalid_transition_returns_409(self, client):
        req_id = _create_request(client)
        # RECEIVED → DISINFECTED 는 건너뛰기 전이(불법)
        r = client.patch(
            f"/api/requests/{req_id}/status", json={"target_status": "DISINFECTED"}
        )
        assert r.status_code == 409, r.text
        assert "허용되지 않은 상태 전이" in r.json()["detail"]

    def test_update_non_received_returns_409(self, client):
        req_id = _create_request(client)
        # RECEIVED → PICKED_UP 으로 전이한 뒤 수정 시도
        r = client.patch(
            f"/api/requests/{req_id}/status", json={"target_status": "PICKED_UP"}
        )
        assert r.status_code == 200, r.text

        r = client.patch(
            f"/api/requests/{req_id}",
            json={
                "pickup_date": "2099-09-02",
                "pickup_location_type": "자택",
                "pickup_address": "주소",
                "electric_bed_quantity": 1,
                "wheelchair_quantity": 0,
                "other_small_quantity": 1,
            },
        )
        assert r.status_code == 409, r.text
        assert "수정 불가" in r.json()["detail"]
