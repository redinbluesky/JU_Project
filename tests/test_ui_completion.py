"""전용 사용자 접수 완료 화면 검증."""

from datetime import date, datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, pool
from sqlalchemy.orm import sessionmaker

from app.main.db.base import Base
from app.main.models.models import (
    BusinessOffice,
    PickupLocationType,
    Request as RequestModel,
    RequestStatus,
)
from app.server import app
import app.server as server_module


@pytest.fixture
def completion_db(monkeypatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=pool.StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autocommit=False, expire_on_commit=False)
    db = factory()
    now = datetime.now(timezone.utc)
    office = BusinessOffice(code="OFFICE_A", name="서울사업소", created_at=now)
    db.add(office)
    db.commit()
    item = RequestModel(
        request_no="R-20260901-0101",
        business_office_id=office.id,
        pickup_date=date(2026, 9, 1),
        pickup_location_type=PickupLocationType.HOME,
        pickup_address="서울시 강남구 테헤란로 123",
        current_status=RequestStatus.RECEIVED,
        electric_bed_quantity=1,
        wheelchair_quantity=2,
        other_small_quantity=0,
        created_at=now,
        updated_at=now,
    )
    db.add(item)
    db.commit()
    monkeypatch.setattr(server_module, "SessionLocal", factory)
    try:
        yield {"id": item.id, "request_no": item.request_no}
    finally:
        db.close()
        engine.dispose()


def test_completion_page_is_dedicated_route_with_request_summary(completion_db):
    with TestClient(app) as client:
        response = client.get(f"/requests/complete/{completion_db['id']}")

    assert response.status_code == 200
    html = response.text
    assert "접수 완료" in html
    for value in (
        completion_db["request_no"],
        "서울사업소",
        "2026-09-01",
        "자택",
        "서울시 강남구 테헤란로 123",
        "전동침대",
        "1",
        "휠체어",
        "2",
        "기타 소형",
        "0",
        "전체 수량",
        "3",
        "접수",
    ):
        assert value in html
    assert 'href="/admin/requests"' in html
    assert 'href="/requests/new"' in html
    assert "/admin/requests/" not in response.url.path


def test_completion_page_returns_404_for_unknown_request(completion_db):
    with TestClient(app) as client:
        response = client.get("/requests/complete/99999")

    assert response.status_code == 404


def test_create_success_redirects_to_completion_route_and_does_not_reset_form():
    js = open("app/static/js/app.js", encoding="utf-8").read()
    assert 'window.location.assign("/requests/complete/" + data.id)' in js
    assert "form.reset()" not in js
