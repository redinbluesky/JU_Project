"""WP-14-B1 — 공통 레이아웃 + 접수폼 UI 검증.

검증 항목:
1. GET /requests/new → 200, HTML 반환.
2. HTML에 label, 사업소 select, 날짜, 장소, 주소, 수량 필드 존재.
3. role="status", aria-live="polite" 존재.
4. /static/css/wanted.css 링크 + Primary token(--wd-primary) 사용.
5. /static/css/app.css, /static/js/app.js 연결.
6. 기존 API 회귀: POST /api/requests 201.

방식: 임시 SQLite(in-memory) + StaticPool + TestClient, get_db 오버라이드.
"""

import re

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
import app.server as server_module


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
def client(test_db, monkeypatch):
    """get_db를 임시 세션으로 오버라이드한 TestClient.

    사업소 옵션은 _office_choices 를 고정 목록으로 치환해
    런타임 DB 상태에 무관하게 결정적으로 렌더링한다.
    """

    def override_get_db():
        yield test_db

    def fake_offices():
        return [
            {"id": 1, "code": "OFFICE_A", "name": "서울사업소"},
            {"id": 2, "code": "OFFICE_B", "name": "부산사업소"},
        ]

    monkeypatch.setattr(server_module, "_office_choices", fake_offices)

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture
def new_page(client):
    resp = client.get("/requests/new")
    assert resp.status_code == 200, resp.text
    return resp.text


def _assert_has(html: str, needle: str, label: str):
    assert needle in html, f"{label} not found: {needle!r}"


class TestNewRequestPage:
    """신규 접수 페이지 렌더링."""

    def test_get_returns_200(self, new_page):
        assert "<html" in new_page.lower() or "<!DOCTYPE" in new_page

    def test_lang_ko(self, new_page):
        assert 'lang="ko"' in new_page

    def test_viewport_meta(self, new_page):
        assert "viewport" in new_page

    def test_wanted_css_link(self, new_page):
        _assert_has(new_page, "/static/css/wanted.css", "wanted.css")

    def test_app_css_link(self, new_page):
        _assert_has(new_page, "/static/css/app.css", "app.css")

    def test_app_js_link(self, new_page):
        _assert_has(new_page, "/static/js/app.js", "app.js")

    def test_header_present(self, new_page):
        assert "app-header" in new_page

    def test_block_content_rendered(self, new_page):
        # form-card = requests/new.html의 content 블록이 렌더링됨
        assert "form-card" in new_page

    def test_live_status_role(self, new_page):
        # role="status"
        assert 'role="status"' in new_page, "role=status missing"
        # aria-live="polite"
        assert 'aria-live="polite"' in new_page, "aria-live=polite missing"

    def test_live_status_container_id(self, new_page):
        assert 'id="live-status"' in new_page


class TestFormFields:
    """접수 폼 필드와 label 검증."""

    def test_office_select(self, new_page):
        assert 'name="business_office_id"' in new_page
        assert 'name="pickup_date"' in new_page
        assert 'name="pickup_location_type"' in new_page
        assert 'name="pickup_address"' in new_page
        assert 'name="electric_bed_quantity"' in new_page
        assert 'name="wheelchair_quantity"' in new_page
        assert 'name="other_small_quantity"' in new_page

    def test_all_inputs_have_labels(self, new_page):
        """모든 input/select 에 명시적 <label for="..."> 존재."""
        # name 속성을 가진 form controls 추출
        controls = re.findall(
            r'<(?:input|select|textarea)[^>]*name="([a-zA-Z0-9_]+)"', new_page
        )
        assert controls, "no named controls found"
        for name in controls:
            # label for="name" 존재 확인
            pattern = f'<label[^>]*for="{name}"'
            assert re.search(pattern, new_page), f"label for={name} missing"

    def test_office_options_rendered(self, new_page):
        # 시딩한 OFFICE_A(서울사업소) 옵션이 렌더링
        assert "서울사업소" in new_page
        assert "OFFICE_A" in new_page

    def test_quantity_inputs(self, new_page):
        # 3개 수량 input 이 모두 number 타입
        qty_names = [
            "electric_bed_quantity",
            "wheelchair_quantity",
            "other_small_quantity",
        ]
        for name in qty_names:
            pattern = rf'<input[^>]*name="{name}"[^>]*type="number"'
            if not re.search(pattern, new_page):
                # 속성 순서 무관 재매칭
                pattern2 = rf'<input[^>]*type="number"[^>]*name="{name}"'
                assert re.search(pattern2, new_page), f"{name} not number input"

    def test_submit_button(self, new_page):
        assert 'type="submit"' in new_page
        assert "접수하기" in new_page

    def test_primary_token_used_in_css(self, new_page, client):
        """app.css 가 Wanted Primary token 을 사용."""
        # 페이지에서 app.css 가 연결되어 있음 (이미 검증) +
        # 실제 CSS 파일에서 --wd-primary 사용 확인
        css_resp = client.get("/static/css/app.css")
        assert css_resp.status_code == 200
        assert "--wd-primary" in css_resp.text, "--wd-primary token not used in app.css"


class TestStaticAssets:
    """정적 리소스 서빙 검증."""

    def test_wanted_css_served(self, client):
        r = client.get("/static/css/wanted.css")
        assert r.status_code == 200

    def test_app_css_served(self, client):
        r = client.get("/static/css/app.css")
        assert r.status_code == 200

    def test_app_js_served(self, client):
        r = client.get("/static/js/app.js")
        assert r.status_code == 200


class TestApiRegression:
    """기존 API 회귀: POST /api/requests 201 유지."""

    def test_create_request_still_works(self, client):
        payload = {
            "business_office_id": 1,
            "pickup_date": "2099-09-01",
            "pickup_location_type": "자택",
            "pickup_address": "서울시 강남구 테헤란로 123",
            "electric_bed_quantity": 1,
            "wheelchair_quantity": 0,
            "other_small_quantity": 2,
        }
        r = client.post("/api/requests", json=payload)
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["request_no"] == "R-0000000001"
        assert body["current_status"] == "RECEIVED"

    def test_list_requests_still_works(self, client):
        r = client.get("/api/requests")
        assert r.status_code == 200, r.text
        assert r.json()["total"] == 0
