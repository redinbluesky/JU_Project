"""WP-14-B2B — 접수 상세 화면 검증.

임시 SQLite + StaticPool 및 FastAPI dependency override를 사용한다.
상세 화면은 server 모듈의 SessionLocal을 직접 사용하므로 해당 참조도
fixture에서 임시 세션으로 교체한다.
"""

import re
from datetime import date, datetime, timezone

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
def detail_db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=pool.StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autocommit=False, expire_on_commit=False)
    db = factory()
    now = datetime(2099, 9, 1, 9, 30, tzinfo=timezone.utc)
    office = BusinessOffice(code="OFFICE_A", name="서울사업소", created_at=now)
    db.add(office)
    db.commit()

    ids = {}
    statuses = [
        ("received", RequestStatus.RECEIVED, None),
        ("picked_up", RequestStatus.PICKED_UP, None),
        ("disinfected", RequestStatus.DISINFECTED, None),
        ("delivered", RequestStatus.DELIVERED, date(2099, 9, 5)),
    ]
    for index, (key, status, completion_date) in enumerate(statuses, start=1):
        request = RequestModel(
            request_no=f"R-20260901-{index:04d}",
            business_office_id=office.id,
            pickup_date=date(2099, 9, index),
            pickup_location_type=PickupLocationType.HOME,
            pickup_address=f"서울시 강남구 테스트로 {index}",
            current_status=status,
            electric_bed_quantity=index,
            wheelchair_quantity=1,
            other_small_quantity=2,
            completion_date=completion_date,
            created_at=now,
            updated_at=now,
        )
        db.add(request)
        db.flush()
        history_statuses = list(RequestStatus)[: list(RequestStatus).index(status) + 1]
        for sequence, history_status in enumerate(history_statuses, start=1):
            db.add(
                RequestStatusHistory(
                    request_id=request.id,
                    status=history_status,
                    changed_at=datetime(2099, 9, sequence, 9, 30, tzinfo=timezone.utc),
                    sequence=sequence,
                )
            )
        db.commit()
        ids[key] = request.id

    yield {"factory": factory, "engine": engine, "ids": ids}
    db.close()
    engine.dispose()


@pytest.fixture
def client(detail_db, monkeypatch):
    def override_get_db():
        db = detail_db["factory"]()
        try:
            yield db
        finally:
            db.close()

    monkeypatch.setattr(server_module, "SessionLocal", detail_db["factory"])
    monkeypatch.setattr(server_module, "engine", detail_db["engine"])
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.pop(get_db, None)


def detail_url(detail_db, key):
    return f"/admin/requests/{detail_db['ids'][key]}"


class TestDetailPage:
    def test_received_detail_200_and_required_information(self, client, detail_db):
        response = client.get(detail_url(detail_db, "received"))
        assert response.status_code == 200, response.text
        html = response.text
        for text in (
            "접수 상세",
            "R-20260901-0001",
            "서울사업소",
            "2099-09-01",
            "자택",
            "서울시 강남구 테스트로 1",
            "전동침대",
            "휠체어",
            "기타 소형",
            "전체 수량",
            "4",
            "접수",
            "생성일시",
            "수정일시",
            "완료일",
            "상태 이력",
            "목록으로 돌아가기",
        ):
            assert text in html, f"missing detail text: {text}"

    def test_detail_timestamps_are_displayed_in_kst(self, client, detail_db):
        html = client.get(detail_url(detail_db, "received")).text
        assert "sequence" in html.lower() or "순번" in html
        assert re.search(r">1<", html)
        # created_at, updated_at, changed_at are stored as 09:30 UTC and shown as 18:30 KST.
        assert html.count("2099-09-01 18:30") == 3
        assert "2099-09-01 09:30" not in html
        assert "접수" in html

    def test_received_has_edit_link_and_next_status_button(self, client, detail_db):
        html = client.get(detail_url(detail_db, "received")).text
        assert re.search(r"/requests/new\?edit_id=\d+", html)
        assert "/api/requests/1" in html
        assert "PICKED_UP" in html
        assert "수거완료" in html
        assert "PATCH" in html or "data-status-action" in html

    def test_received_does_not_have_pdf_button(self, client, detail_db):
        html = client.get(detail_url(detail_db, "received")).text
        assert "/api/requests/1/pdf" not in html
        assert "PDF 다운로드" not in html

    def test_disinfected_has_pdf_button(self, client, detail_db):
        html = client.get(detail_url(detail_db, "disinfected")).text
        assert "/api/requests/3/pdf" in html
        assert "PDF 다운로드" in html

    def test_delivered_has_completion_date_and_pdf(self, client, detail_db):
        html = client.get(detail_url(detail_db, "delivered")).text
        assert "2099-09-05" in html
        assert "/api/requests/4/pdf" in html
        assert "PDF 다운로드" in html
        assert "다음 상태" not in html

    def test_status_badge_and_accessibility(self, client, detail_db):
        html = client.get(detail_url(detail_db, "received")).text
        assert "status-badge" in html
        assert 'role="status"' in html
        assert 'aria-live="polite"' in html

    def test_not_found_is_safe_404_template(self, client):
        response = client.get("/admin/requests/999999")
        assert response.status_code == 404
        html = response.text
        assert "접수를 찾을 수 없습니다" in html or "존재하지 않는 접수" in html
        assert "Traceback" not in html
        assert "목록으로 돌아가기" in html


class TestDetailStaticAndRegression:
    def test_css_and_js_links(self, client, detail_db):
        html = client.get(detail_url(detail_db, "received")).text
        assert "/static/css/wanted.css" in html
        assert "/static/css/app.css" in html
        assert "/static/js/app.js" in html

    def test_list_page_still_works(self, client):
        response = client.get("/admin/requests")
        assert response.status_code == 200
        assert "접수 목록" in response.text

    def test_new_request_page_still_works(self, client):
        response = client.get("/requests/new")
        assert response.status_code == 200
        assert "접수하기" in response.text

    def test_existing_list_api_still_works(self, client):
        response = client.get("/api/requests")
        assert response.status_code == 200
        assert response.json()["total"] == 4

    def test_detail_js_asset_served(self, client):
        response = client.get("/static/js/app.js")
        assert response.status_code == 200
        assert "fetch" in response.text
