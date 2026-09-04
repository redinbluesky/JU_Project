"""Request 수정 API (PATCH) pytest 테스트.
임시 SQLite DB + FastAPI TestClient + get_db 의존성 오버라이드로
runtime/db/ju-project.db를 오염시키지 않는다.
"""

import pytest
from datetime import date, datetime, timedelta, timezone
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import pool

from app.main.db.base import Base
from app.main.models.models import (
    Request,
    BusinessOffice,
    RequestStatus,
    RequestNoCounter,
)
from app.main.api.requests import get_db
from app.server import app


@pytest.fixture
def test_db():
    """임시 SQLite DB 세션 생성 + 초기 데이터(사업소, 카운터) 시딩.
    StaticPool로 단일 연결을 공유 → TestClient의 별도 스레드에서도 같은 DB.
    """
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

    # 카운터 테이블 초기화 (id=1, current_value=0)
    db.add(RequestNoCounter(id=1, current_value=0))
    db.commit()

    yield db

    db.close()


@pytest.fixture
def client(test_db):
    """get_db를 임시 세션으로 오버라이드한 TestClient"""

    def override_get_db():
        yield test_db

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.pop(get_db, None)


def _create_payload() -> dict:
    """정상 POST 입력"""
    return {
        "business_office_id": 1,
        "pickup_date": "2099-09-01",
        "pickup_location_type": "자택",
        "pickup_address": "서울시 강남구 테헤란로 123",
        "electric_bed_quantity": 1,
        "wheelchair_quantity": 0,
        "other_small_quantity": 2,
    }


@pytest.fixture
def created_request_id(client):
    """RECEIVED 상태 접수를 1건 생성하고 id 반환"""
    r = client.post("/api/requests", json=_create_payload())
    assert r.status_code == 201, r.text
    return r.json()["id"]


class TestPatchSuccess:
    """RECEIVED 접수 PATCH 성공 (200)"""

    def test_patch_received_returns_200(self, client, created_request_id):
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
        body = r.json()
        assert body["id"] == created_request_id
        assert body["pickup_date"] == "2026-09-10"
        assert body["pickup_location_type"] == "사업소"
        assert body["pickup_address"] == "부산시 해운대구 센텀중앙로 456"
        assert body["electric_bed_quantity"] == 2
        assert body["wheelchair_quantity"] == 1
        assert body["other_small_quantity"] == 3
        assert body["current_status"] == "RECEIVED"


class TestPatchPersistsToDB:
    """수정된 모든 필드가 실제로 DB에 저장되는지 확인"""

    def test_all_fields_persisted(self, client, test_db, created_request_id):
        payload = {
            "pickup_date": "2026-10-05",
            "pickup_location_type": "사업소",
            "pickup_address": "제주특별자치도 제주시 아라일주로 100",
            "electric_bed_quantity": 5,
            "wheelchair_quantity": 4,
            "other_small_quantity": 3,
        }
        r = client.patch(f"/api/requests/{created_request_id}", json=payload)
        assert r.status_code == 200, r.text

        # 세션 캐시 무시하고 DB에서 직접 재조회
        test_db.expire_all()
        req = test_db.get(Request, created_request_id)
        assert req is not None
        assert req.pickup_date == date(2026, 10, 5)
        assert req.pickup_location_type.value == "사업소"
        assert req.pickup_address == "제주특별자치도 제주시 아라일주로 100"
        assert req.electric_bed_quantity == 5
        assert req.wheelchair_quantity == 4
        assert req.other_small_quantity == 3
        assert req.updated_at is not None


class TestBusinessOfficeNotEditable:
    """business_office_id는 수정 불가 (요청에 포함해도 무시)"""

    def test_business_office_id_unchanged(self, client, test_db, created_request_id):
        payload = {
            "pickup_date": "2026-09-20",
            "pickup_location_type": "자택",
            "pickup_address": "서울시 마포구 월드컵로 77",
            "electric_bed_quantity": 2,
            "wheelchair_quantity": 0,
            "other_small_quantity": 1,
            # 아래는 RequestUpdate 스키마에 없는 필드 → 무시되어야 함
            "business_office_id": 2,
        }
        r = client.patch(f"/api/requests/{created_request_id}", json=payload)
        assert r.status_code == 200, r.text

        test_db.expire_all()
        req = test_db.get(Request, created_request_id)
        assert req.business_office_id == 1  # 그대로 1 유지
        assert r.json()["business_office_id"] == 1


class TestPatchForbiddenStatus:
    """PICKED_UP 상태 접수는 PATCH 시 409"""

    def test_patch_picked_up_returns_409(self, client, test_db, created_request_id):
        # 상태를 직접 PICKED_UP으로 변경
        req = test_db.get(Request, created_request_id)
        req.current_status = RequestStatus.PICKED_UP
        test_db.commit()

        payload = {
            "pickup_date": "2026-09-15",
            "pickup_location_type": "자택",
            "pickup_address": "서울시 강남구 테헤란로 123",
            "electric_bed_quantity": 1,
            "wheelchair_quantity": 0,
            "other_small_quantity": 2,
        }
        r = client.patch(f"/api/requests/{created_request_id}", json=payload)
        assert r.status_code == 409
        assert "수정 불가" in r.json()["detail"]


class TestPatchNotFound:
    """존재하지 않는 id는 409"""

    def test_patch_missing_id_returns_409(self, client):
        payload = {
            "pickup_date": "2026-09-15",
            "pickup_location_type": "자택",
            "pickup_address": "서울시 강남구 테헤란로 123",
            "electric_bed_quantity": 1,
            "wheelchair_quantity": 0,
            "other_small_quantity": 2,
        }
        r = client.patch("/api/requests/99999", json=payload)
        assert r.status_code == 409
        assert "존재하지 않는 접수" in r.json()["detail"]


class TestPatchValidation422:
    """날짜/수량 검증 실패는 API 422"""

    @pytest.fixture
    def valid_payload(self):
        return {
            "pickup_date": "2026-09-15",
            "pickup_location_type": "자택",
            "pickup_address": "서울시 강남구 테헤란로 123",
            "electric_bed_quantity": 1,
            "wheelchair_quantity": 0,
            "other_small_quantity": 2,
        }

    def test_patch_today_date_returns_422(self, client, created_request_id, valid_payload):
        valid_payload["pickup_date"] = date.today().isoformat()
        r = client.patch(f"/api/requests/{created_request_id}", json=valid_payload)
        assert r.status_code == 422

    def test_patch_past_date_returns_422(self, client, created_request_id, valid_payload):
        valid_payload["pickup_date"] = (date.today() - timedelta(days=1)).isoformat()
        r = client.patch(f"/api/requests/{created_request_id}", json=valid_payload)
        assert r.status_code == 422

    def test_patch_all_zero_quantities_returns_422(self, client, created_request_id, valid_payload):
        valid_payload["electric_bed_quantity"] = 0
        valid_payload["wheelchair_quantity"] = 0
        valid_payload["other_small_quantity"] = 0
        r = client.patch(f"/api/requests/{created_request_id}", json=valid_payload)
        assert r.status_code == 422

    def test_patch_negative_quantity_returns_422(self, client, created_request_id, valid_payload):
        valid_payload["electric_bed_quantity"] = -1
        r = client.patch(f"/api/requests/{created_request_id}", json=valid_payload)
        assert r.status_code == 422

    def test_patch_validation_failure_does_not_modify(self, client, test_db, created_request_id, valid_payload):
        """422 발생 시 기존 데이터 유지"""
        before = test_db.get(Request, created_request_id)
        old_address = before.pickup_address
        old_bed = before.electric_bed_quantity

        valid_payload["pickup_date"] = date.today().isoformat()
        r = client.patch(f"/api/requests/{created_request_id}", json=valid_payload)
        assert r.status_code == 422

        test_db.expire_all()
        after = test_db.get(Request, created_request_id)
        assert after.pickup_address == old_address
        assert after.electric_bed_quantity == old_bed
