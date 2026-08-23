"""WP-10 통계 집계 API 테스트.

- 임시 SQLite(in-memory) + StaticPool 단일 연결 + TestClient + get_db 오버라이드
- 사업소 2개 + 서로 다른 pickup_date/상태를 가진 접수 4건 시딩
- 각 테스트는 API 결과를 SQLAlchemy 집계 쿼리(group_by/sum/count)로 직접
  계산한 기대값과 대조한다. (서비스 구현과 독립적인 계산 경로)

시딩 설계 (생성 순서 id 1..4):
  r1: office 1, D1(today+7),  RECEIVED,  (electric 1, wheelchair 2, other 3)
  r2: office 1, D2(today+10), PICKED_UP, (electric 4, wheelchair 5, other 0)
  r3: office 2, D3(today+12), DISINFECTED, (electric 7, wheelchair 0, other 2)
  r4: office 2, D4(today+20), DELIVERED, (electric 0, wheelchair 1, other 5)
"""

import pytest
from datetime import date, datetime, timedelta, timezone
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select, pool
from sqlalchemy.orm import sessionmaker

from app.main.db.base import Base
from app.main.models.models import BusinessOffice, Request, RequestNoCounter, RequestStatus
from app.main.api.requests import get_db
from app.server import app

ALL_STATUS_KEYS = ["RECEIVED", "PICKED_UP", "DISINFECTED", "DELIVERED"]

# 서로 다른 수거희망일 (오늘 기준 미래)
D1 = (date.today() + timedelta(days=7)).isoformat()
D2 = (date.today() + timedelta(days=10)).isoformat()
D3 = (date.today() + timedelta(days=12)).isoformat()
D4 = (date.today() + timedelta(days=20)).isoformat()


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


def _payload(office_id: int, pickup_date: str, seq: int, eb: int, wc: int, os_: int) -> dict:
    return {
        "business_office_id": office_id,
        "pickup_date": pickup_date,
        "pickup_location_type": "자택",
        "pickup_address": f"통계시딩주소-{seq}",
        "electric_bed_quantity": eb,
        "wheelchair_quantity": wc,
        "other_small_quantity": os_,
    }


@pytest.fixture
def seeded(client):
    """접수 4건 시딩 + 상태 전이로 4개 상태 확보.

    r1: office 1, D1, RECEIVED
    r2: office 1, D2, PICKED_UP
    r3: office 2, D3, DISINFECTED
    r4: office 2, D4, DELIVERED
    """
    ids = {}
    specs = (
        ("r1", 1, D1, 1, 2, 3),
        ("r2", 1, D2, 4, 5, 0),
        ("r3", 2, D3, 7, 0, 2),
        ("r4", 2, D4, 0, 1, 5),
    )
    for i, (key, office, d, eb, wc, os_) in enumerate(specs, start=1):
        r = client.post("/api/requests", json=_payload(office, d, i, eb, wc, os_))
        assert r.status_code == 201, r.text
        ids[key] = r.json()["id"]

    r = client.patch(f"/api/requests/{ids['r2']}/status", json={"target_status": "PICKED_UP"})
    assert r.status_code == 200, r.text
    r = client.patch(f"/api/requests/{ids['r3']}/status", json={"target_status": "PICKED_UP"})
    assert r.status_code == 200, r.text
    r = client.patch(f"/api/requests/{ids['r3']}/status", json={"target_status": "DISINFECTED"})
    assert r.status_code == 200, r.text
    r = client.patch(f"/api/requests/{ids['r4']}/status", json={"target_status": "PICKED_UP"})
    assert r.status_code == 200, r.text
    r = client.patch(f"/api/requests/{ids['r4']}/status", json={"target_status": "DISINFECTED"})
    assert r.status_code == 200, r.text
    r = client.patch(f"/api/requests/{ids['r4']}/status", json={"target_status": "DELIVERED"})
    assert r.status_code == 200, r.text

    return ids


def _status_name(v):
    """enum 인스턴스든 문자열이든 상태 이름으로 정규화."""
    return v.value if isinstance(v, RequestStatus) else str(v)


def _db_expected(
    db,
    pickup_date_from: str | None = None,
    pickup_date_to: str | None = None,
    business_office_id: int | None = None,
    current_status: str | None = None,
) -> dict:
    """기대값을 SQLAlchemy 집계 쿼리로 직접 계산 (서비스와 독립).

    count / group_by / sum 쿼리로 집계하며, 빈 집계도 동일한 구조를 만든다.
    """
    def apply(stmt):
        if pickup_date_from is not None:
            stmt = stmt.where(Request.pickup_date >= pickup_date_from)
        if pickup_date_to is not None:
            stmt = stmt.where(Request.pickup_date <= pickup_date_to)
        if business_office_id is not None:
            stmt = stmt.where(Request.business_office_id == business_office_id)
        if current_status is not None:
            stmt = stmt.where(Request.current_status == current_status)
        return stmt

    total = db.execute(
        apply(select(func.count(Request.id)).select_from(Request))
    ).scalar_one()

    office_rows = db.execute(
        apply(
            select(Request.business_office_id, func.count(Request.id))
            .select_from(Request)
            .group_by(Request.business_office_id)
        )
    ).all()
    by_business_office = {str(oid): n for oid, n in office_rows}

    status_rows = db.execute(
        apply(
            select(Request.current_status, func.count(Request.id))
            .select_from(Request)
            .group_by(Request.current_status)
        )
    ).all()
    by_status = {s: 0 for s in ALL_STATUS_KEYS}
    for st, n in status_rows:
        by_status[_status_name(st)] = n

    eb, wc, os_ = db.execute(
        apply(
            select(
                func.coalesce(func.sum(Request.electric_bed_quantity), 0),
                func.coalesce(func.sum(Request.wheelchair_quantity), 0),
                func.coalesce(func.sum(Request.other_small_quantity), 0),
            ).select_from(Request)
        )
    ).one()

    return {
        "total_requests": int(total),
        "by_business_office": by_business_office,
        "by_status": by_status,
        "quantities": {
            "electric_bed": int(eb),
            "wheelchair": int(wc),
            "other_small": int(os_),
            "total": int(eb) + int(wc) + int(os_),
        },
    }


def _get_stats(client, **params):
    r = client.get("/api/statistics", params=params)
    assert r.status_code == 200, r.text
    return r.json()


class TestTotalRequests:
    """1. 전체 접수 건수"""

    def test_total_requests_all(self, client, seeded, test_db):
        body = _get_stats(client)
        expected = _db_expected(test_db)
        assert body["total_requests"] == expected["total_requests"]
        assert body["total_requests"] == 4


class TestByBusinessOffice:
    """2. 사업소별 집계 (실제 존재하는 사업소만 포함)"""

    def test_by_business_office_all(self, client, seeded, test_db):
        body = _get_stats(client)
        expected = _db_expected(test_db)
        assert body["by_business_office"] == expected["by_business_office"]
        assert body["by_business_office"] == {"1": 2, "2": 2}


class TestByStatus:
    """3. 상태별 집계 (네 상태 키 항상 존재)"""

    def test_by_status_all(self, client, seeded, test_db):
        body = _get_stats(client)
        expected = _db_expected(test_db)
        assert body["by_status"] == expected["by_status"]
        assert body["by_status"] == {
            "RECEIVED": 1, "PICKED_UP": 1, "DISINFECTED": 1, "DELIVERED": 1,
        }
        for key in ALL_STATUS_KEYS:
            assert key in body["by_status"]


class TestQuantities:
    """4. 전체·품목별 수량 및 합계"""

    def test_quantities_all(self, client, seeded, test_db):
        body = _get_stats(client)
        expected = _db_expected(test_db)
        assert body["quantities"] == expected["quantities"]
        # r1(1,2,3) + r2(4,5,0) + r3(7,0,2) + r4(0,1,5)
        assert body["quantities"] == {
            "electric_bed": 12,
            "wheelchair": 8,
            "other_small": 10,
            "total": 30,
        }


class TestDateRangeFilter:
    """5. pickup_date 기간 필터 집계"""

    def test_date_range_filter(self, client, seeded, test_db):
        # D1~D3 구간: r1(D1), r2(D2), r3(D3)만 포함
        body = _get_stats(client, pickup_date_from=D1, pickup_date_to=D3)
        expected = _db_expected(test_db, pickup_date_from=D1, pickup_date_to=D3)
        assert body == expected
        assert body["total_requests"] == 3
        assert body["by_status"] == {
            "RECEIVED": 1, "PICKED_UP": 1, "DISINFECTED": 1, "DELIVERED": 0,
        }


class TestOfficeFilter:
    """6. 사업소 필터 집계"""

    def test_office_filter(self, client, seeded, test_db):
        body = _get_stats(client, business_office_id=1)
        expected = _db_expected(test_db, business_office_id=1)
        assert body == expected
        assert body["total_requests"] == 2
        assert body["by_business_office"] == {"1": 2}
        # office 1: r1(1,2,3) + r2(4,5,0)
        assert body["quantities"] == {
            "electric_bed": 5, "wheelchair": 7, "other_small": 3, "total": 15,
        }


class TestCombinedStatusDateFilter:
    """7. 상태+기간 복합 필터 집계 (AND 결합)"""

    def test_combined_status_date_filter(self, client, seeded, test_db):
        # PICKED_UP + D1~D3 → r2(D2)만 해당
        body = _get_stats(
            client,
            current_status="PICKED_UP",
            pickup_date_from=D1,
            pickup_date_to=D3,
        )
        expected = _db_expected(
            test_db,
            current_status="PICKED_UP",
            pickup_date_from=D1,
            pickup_date_to=D3,
        )
        assert body == expected
        assert body["total_requests"] == 1
        assert body["by_business_office"] == {"1": 1}
        assert body["by_status"] == {
            "RECEIVED": 0, "PICKED_UP": 1, "DISINFECTED": 0, "DELIVERED": 0,
        }
        # r2: electric 4, wheelchair 5, other 0
        assert body["quantities"] == {
            "electric_bed": 4, "wheelchair": 5, "other_small": 0, "total": 9,
        }


class TestInvalidRange:
    """8. from > to 거부 (422)"""

    def test_from_after_to_rejected(self, client, seeded):
        r = client.get(
            "/api/statistics",
            params={"pickup_date_from": D2, "pickup_date_to": D1},
        )
        assert r.status_code == 422, r.text


class TestZeroResultStructure:
    """9. 0건 필터 결과도 응답 구조 유지"""

    def test_zero_result_keeps_structure(self, client, seeded, test_db):
        # 데이터 없는 먼 미래 구간
        far_from = (date.today() + timedelta(days=365)).isoformat()
        far_to = (date.today() + timedelta(days=366)).isoformat()
        body = _get_stats(client, pickup_date_from=far_from, pickup_date_to=far_to)
        expected = _db_expected(test_db, pickup_date_from=far_from, pickup_date_to=far_to)
        assert body == expected
        assert body["total_requests"] == 0
        assert body["by_business_office"] == {}
        assert body["by_status"] == {
            "RECEIVED": 0, "PICKED_UP": 0, "DISINFECTED": 0, "DELIVERED": 0,
        }
        assert body["quantities"] == {
            "electric_bed": 0, "wheelchair": 0, "other_small": 0, "total": 0,
        }


class TestConsistencyWithListApi:
    """10. 목록 API의 동일 필터 결과와 통계 total 일치"""

    def test_total_matches_list_api(self, client, seeded):
        cases = [
            {},
            {"pickup_date_from": D1, "pickup_date_to": D3},
            {"business_office_id": 2},
            {"current_status": "RECEIVED"},
            {"pickup_date_from": D1, "current_status": "RECEIVED"},
            {"business_office_id": 2, "pickup_date_from": D2},
        ]
        for params in cases:
            stats = client.get("/api/statistics", params=params)
            assert stats.status_code == 200, stats.text
            listing = client.get("/api/requests", params=params)
            assert listing.status_code == 200, listing.text
            assert stats.json()["total_requests"] == listing.json()["total"]
