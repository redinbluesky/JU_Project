"""WP-08-A 접수 목록/상세/필터 조회 API 테스트.

- 임시 SQLite(in-memory) + StaticPool 단일 연결 + TestClient + get_db 오버라이드
- 사업소 2개 + 서로 다른 pickup_date/status의 접수 4건 시딩
- 범위: 목록 정렬/기간(pickup_date 기준)/사업소/상태/복합 필터, from>to 거부,
        상세 200/404, 기존 POST·PATCH 수정·status API 회귀
"""

import pytest
from datetime import date, datetime, timedelta, timezone
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import pool

from app.main.db.base import Base
from app.main.models.models import BusinessOffice, RequestNoCounter
from app.main.api.requests import get_db
from app.server import app


@pytest.fixture
def test_db():
    """임시 SQLite 세션 + 사업소 2개/카운터 시딩 (StaticPool 단일 연결 공유)."""
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
    db.add(BusinessOffice(code="OFFICE_B", name="부산사업소", created_at=now))
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


# pickup_date는 today + N일로 동적 설정 (생성 시점 created_at은 항상 그보다 과거)
D1 = (date.today() + timedelta(days=7)).isoformat()    # r1 (office 1)
D3 = (date.today() + timedelta(days=9)).isoformat()    # r3 (office 2)
D2 = (date.today() + timedelta(days=10)).isoformat()   # r2 (office 1)
D4 = (date.today() + timedelta(days=20)).isoformat()   # r4 (office 2)


def _payload(office_id: int, pickup_date: str, seq: int) -> dict:
    return {
        "business_office_id": office_id,
        "pickup_date": pickup_date,
        "pickup_location_type": "자택",
        "pickup_address": f"시딩주소-{seq}",
        "electric_bed_quantity": 1,
        "wheelchair_quantity": 0,
        "other_small_quantity": seq,
    }


@pytest.fixture
def seeded(client):
    """접수 4건 시딩.

    r1: office 1, D1, RECEIVED
    r2: office 1, D2, PICKED_UP
    r3: office 2, D3, RECEIVED
    r4: office 2, D4, DISINFECTED
    (생성 순서이므로 id: r1=1, r2=2, r3=3, r4=4)
    """
    ids = {}
    specs = (("r1", 1, D1), ("r2", 1, D2), ("r3", 2, D3), ("r4", 2, D4))
    for i, (key, office, d) in enumerate(specs, start=1):
        r = client.post("/api/requests", json=_payload(office, d, i))
        assert r.status_code == 201, r.text
        ids[key] = r.json()["id"]

    r = client.patch(f"/api/requests/{ids['r2']}/status", json={"target_status": "PICKED_UP"})
    assert r.status_code == 200, r.text
    r = client.patch(f"/api/requests/{ids['r4']}/status", json={"target_status": "PICKED_UP"})
    assert r.status_code == 200, r.text
    r = client.patch(f"/api/requests/{ids['r4']}/status", json={"target_status": "DISINFECTED"})
    assert r.status_code == 200, r.text

    return ids


def _ids(body: dict) -> list[int]:
    return [item["id"] for item in body["items"]]


class TestListAll:
    """1. 전체 목록 개수·정렬 (pickup_date ASC, id ASC)"""

    def test_full_list_count_and_order(self, client, seeded):
        r = client.get("/api/requests")
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["total"] == 4
        # pickup_date: r1(D1) < r3(D3) < r2(D2) < r4(D4)
        assert _ids(body) == [seeded["r1"], seeded["r3"], seeded["r2"], seeded["r4"]]


class TestDateRangeFilter:
    """2. pickup_date_from: 생성일이 아닌 수거희망일 기준 동작"""

    def test_from_to_window_uses_pickup_date(self, client, seeded):
        # created_at(=오늘)은 D1보다 과거. created_at 기준으로 걸렀다면 0건이 됨.
        r = client.get("/api/requests", params={"pickup_date_from": D1, "pickup_date_to": D3})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["total"] == 2
        assert _ids(body) == [seeded["r1"], seeded["r3"]]

        # 결과를 실제로 확인: 두 건 모두 created_at < D1 이고 pickup_date가 구간 안에 있음
        for item in body["items"]:
            assert item["created_at"] < f"{D1}T00:00:00"
            assert item["pickup_date"] in (D1, D3)


class TestDateToFilter:
    """3. pickup_date_to 필터"""

    def test_to_filter(self, client, seeded):
        r = client.get("/api/requests", params={"pickup_date_to": D3})
        assert r.status_code == 200, r.text
        body = r.json()
        assert _ids(body) == [seeded["r1"], seeded["r3"]]

    def test_from_filter(self, client, seeded):
        r = client.get("/api/requests", params={"pickup_date_from": D2})
        assert r.status_code == 200, r.text
        body = r.json()
        assert _ids(body) == [seeded["r2"], seeded["r4"]]


class TestBusinessOfficeFilter:
    """4. 사업소 필터"""

    def test_office_filter(self, client, seeded):
        r1 = client.get("/api/requests", params={"business_office_id": 1})
        assert r1.status_code == 200, r1.text
        assert _ids(r1.json()) == [seeded["r1"], seeded["r2"]]

        r2 = client.get("/api/requests", params={"business_office_id": 2})
        assert r2.status_code == 200, r2.text
        assert _ids(r2.json()) == [seeded["r3"], seeded["r4"]]


class TestStatusFilter:
    """5. 상태 필터"""

    def test_status_filter(self, client, seeded):
        r1 = client.get("/api/requests", params={"current_status": "RECEIVED"})
        assert r1.status_code == 200, r1.text
        assert _ids(r1.json()) == [seeded["r1"], seeded["r3"]]

        r2 = client.get("/api/requests", params={"current_status": "PICKED_UP"})
        assert r2.status_code == 200, r2.text
        assert _ids(r2.json()) == [seeded["r2"]]

        r3 = client.get("/api/requests", params={"current_status": "DISINFECTED"})
        assert r3.status_code == 200, r3.text
        assert _ids(r3.json()) == [seeded["r4"]]

        r4 = client.get("/api/requests", params={"current_status": "DELIVERED"})
        assert r4.status_code == 200, r4.text
        assert r4.json()["total"] == 0
        assert r4.json()["items"] == []


class TestCombinedFilter:
    """6. 기간 + 사업소 + 상태 복합 필터 (AND 결합)"""

    def test_combined_filter(self, client, seeded):
        # D1~D2, office 1, RECEIVED → r1 만 해당 (r2는 PICKED_UP)
        r = client.get(
            "/api/requests",
            params={
                "pickup_date_from": D1,
                "pickup_date_to": D2,
                "business_office_id": 1,
                "current_status": "RECEIVED",
            },
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["total"] == 1
        assert _ids(body) == [seeded["r1"]]


class TestInvalidRange:
    """7. from > to 명시적 거부 (422/400)"""

    def test_from_after_to_rejected(self, client, seeded):
        r = client.get(
            "/api/requests",
            params={"pickup_date_from": D2, "pickup_date_to": D1},
        )
        assert r.status_code in (400, 422), r.text


class TestDetail:
    """8. 상세 200 + 전체 필수 필드 확인"""

    def test_detail_200_all_fields(self, client, seeded):
        r = client.get(f"/api/requests/{seeded['r1']}")
        assert r.status_code == 200, r.text
        body = r.json()

        expected_keys = {
            "id", "request_no", "business_office_id", "pickup_date",
            "pickup_location_type", "pickup_address", "current_status",
            "electric_bed_quantity", "wheelchair_quantity",
            "other_small_quantity", "completion_date", "created_at",
            "updated_at",
        }
        assert expected_keys <= set(body.keys())

        assert body["id"] == seeded["r1"]
        assert body["request_no"].startswith("R-")
        assert body["business_office_id"] == 1
        assert body["pickup_date"] == D1
        assert body["pickup_location_type"] == "자택"
        assert body["pickup_address"] == "시딩주소-1"
        assert body["current_status"] == "RECEIVED"
        assert body["electric_bed_quantity"] == 1
        assert body["wheelchair_quantity"] == 0
        assert body["other_small_quantity"] == 1
        assert body["completion_date"] is None
        assert body["created_at"]
        assert body["updated_at"]

    def test_detail_delivered_has_completion_date(self, client, seeded):
        """DELIVERED 접수는 completion_date 기록됨 (r4는 DISINFECTED → None)"""
        rid = seeded["r4"]
        r = client.patch(
            f"/api/requests/{rid}/status", json={"target_status": "DELIVERED"}
        )
        assert r.status_code == 200, r.text

        d = client.get(f"/api/requests/{rid}")
        assert d.status_code == 200, d.text
        body = d.json()
        assert body["current_status"] == "DELIVERED"
        assert body["completion_date"] is not None


class TestDetailNotFound:
    """9. 미존재 상세 404"""

    def test_detail_not_found_404(self, client, seeded):
        r = client.get("/api/requests/99999")
        assert r.status_code == 404, r.text
        assert "존재하지 않는 접수" in r.json()["detail"]


class TestExistingApisRegression:
    """10. 기존 POST/PATCH 수정/status API 회귀"""

    def test_post_create_still_works(self, client, seeded):
        r = client.post("/api/requests", json=_payload(1, D4, 99))
        assert r.status_code == 201, r.text
        assert r.json()["current_status"] == "RECEIVED"

    def test_patch_update_still_works(self, client, seeded):
        payload = {
            "pickup_date": D4,
            "pickup_location_type": "사업소",
            "pickup_address": "수정주소",
            "electric_bed_quantity": 0,
            "wheelchair_quantity": 2,
            "other_small_quantity": 1,
        }
        r = client.patch(f"/api/requests/{seeded['r1']}", json=payload)
        assert r.status_code == 200, r.text
        assert r.json()["pickup_address"] == "수정주소"
        assert r.json()["wheelchair_quantity"] == 2

    def test_status_api_still_works(self, client, seeded):
        r = client.patch(
            f"/api/requests/{seeded['r1']}/status",
            json={"target_status": "PICKED_UP"},
        )
        assert r.status_code == 200, r.text
        assert r.json()["current_status"] == "PICKED_UP"
