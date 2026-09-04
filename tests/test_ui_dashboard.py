"""WP-14-B3B — 통계 대시보드 화면 검증."""

from datetime import date, datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, pool
from sqlalchemy.orm import sessionmaker

from app.main.api.requests import get_db
from app.main.db.base import Base
from app.main.models.models import (
    BusinessOffice,
    PickupLocationType,
    Request as RequestModel,
    RequestStatus,
    RequestStatusHistory,
)
from app.server import app
import app.server as server_module


@pytest.fixture
def dashboard_db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=pool.StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autocommit=False, expire_on_commit=False)
    db = factory()
    now = datetime(2099, 9, 1, 9, 30, tzinfo=timezone.utc)
    offices = [
        BusinessOffice(code="OFFICE_A", name="서울사업소", created_at=now),
        BusinessOffice(code="OFFICE_B", name="부산사업소", created_at=now),
    ]
    db.add_all(offices)
    db.commit()

    rows = [
        (offices[0].id, date(2099, 9, 1), RequestStatus.RECEIVED, 1, 1, 1),
        (offices[0].id, date(2099, 9, 2), RequestStatus.PICKED_UP, 2, 1, 2),
        (offices[1].id, date(2099, 9, 3), RequestStatus.DISINFECTED, 3, 1, 3),
        (offices[1].id, date(2099, 9, 4), RequestStatus.DELIVERED, 4, 1, 2),
    ]
    for index, (office_id, pickup_date, status, bed, wheelchair, other) in enumerate(rows, start=1):
        item = RequestModel(
            request_no=f"R-20260901-{index:04d}",
            business_office_id=office_id,
            pickup_date=pickup_date,
            pickup_location_type=PickupLocationType.HOME,
            pickup_address=f"테스트 주소 {index}",
            current_status=status,
            electric_bed_quantity=bed,
            wheelchair_quantity=wheelchair,
            other_small_quantity=other,
            created_at=now,
            updated_at=now,
        )
        db.add(item)
        db.flush()
        db.add(
            RequestStatusHistory(
                request_id=item.id,
                status=status,
                changed_at=now,
                sequence=1,
            )
        )
    db.commit()
    yield {"factory": factory, "engine": engine}
    db.close()
    engine.dispose()


@pytest.fixture
def client(dashboard_db, monkeypatch):
    def override_get_db():
        db = dashboard_db["factory"]()
        try:
            yield db
        finally:
            db.close()

    monkeypatch.setattr(server_module, "SessionLocal", dashboard_db["factory"])
    monkeypatch.setattr(server_module, "engine", dashboard_db["engine"])
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.pop(get_db, None)


class TestDashboardPage:
    def test_dashboard_returns_200_and_renders_statistics(self, client):
        response = client.get("/admin/dashboard")
        assert response.status_code == 200, response.text
        html = response.text
        for text in (
            "통계 대시보드",
            "전체 접수 건수",
            "사업소별 접수 건수",
            "상태별 접수 건수",
            "전동침대",
            "휠체어",
            "기타 소형",
            "전체 수량",
            "서울사업소",
            "부산사업소",
            "접수",
            "수거완료",
            "소독완료",
            "배달완료",
        ):
            assert text in html, f"missing dashboard text: {text}"
        assert "4건" in html
        assert ">22<" in html or ">22건<" in html

    def test_dashboard_renders_item_and_office_values(self, client):
        html = client.get("/admin/dashboard").text
        assert ">10<" in html  # 전동침대 합계
        assert ">4<" in html  # 휠체어 합계
        assert ">8<" in html  # 기타 소형 합계
        assert "서울사업소" in html and "부산사업소" in html
        assert html.count("1건") >= 2

    def test_date_filter_values_are_preserved_and_change_statistics(self, client):
        response = client.get(
            "/admin/dashboard?pickup_date_from=2099-09-02&pickup_date_to=2099-09-03"
        )
        assert response.status_code == 200
        html = response.text
        assert 'value="2099-09-02"' in html
        assert 'value="2099-09-03"' in html
        assert "2건" in html
        assert ">5<" in html  # bed: 2 + 3
        assert ">2<" in html  # wheelchair: 1 + 1
        assert ">5<" in html  # other: 2 + 3
        assert ">12<" in html  # total quantity
        assert "서울사업소" in html and "부산사업소" in html

    def test_empty_result_has_safe_empty_state(self, client):
        response = client.get(
            "/admin/dashboard?pickup_date_from=2030-01-01&pickup_date_to=2030-01-31"
        )
        assert response.status_code == 200
        html = response.text
        assert "해당 기간의 접수 내역이 없습니다." in html
        assert "기간을 조정하거나 필터를 초기화해 주세요." in html
        assert "Traceback" not in html
        assert ">0<" in html or "0건" in html

    def test_dashboard_accessibility_and_wanted_css(self, client):
        html = client.get("/admin/dashboard").text
        assert 'role="status"' in html
        assert 'aria-live="polite"' in html
        assert '/static/css/wanted.css' in html
        assert '/static/css/app.css' in html
        assert "status-badge" in html
        assert "status-badge__dot" in html


class TestDashboardResponsiveAndRegression:
    def test_dashboard_css_has_mobile_one_column_and_no_horizontal_scroll(self):
        css = Path("app/static/css/app.css").read_text(encoding="utf-8")
        assert "@media (max-width: 720px)" in css
        assert ".detail-grid" in css
        assert "grid-template-columns: 1fr" in css
        assert "overflow-x: hidden" in css

    def test_existing_pages_and_api_still_respond(self, client):
        assert client.get("/requests/new").status_code == 200
        assert client.get("/admin/requests").status_code == 200
        assert client.get("/admin/requests/1").status_code == 200
        statistics = client.get("/api/statistics")
        assert statistics.status_code == 200
        assert statistics.json()["total_requests"] == 4
