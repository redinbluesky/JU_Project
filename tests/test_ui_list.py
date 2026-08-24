"""WP-14-B2A — 접수 목록 화면 검증 (테스트만 추가, 앱 코드 미수정).

검증 항목:
1. GET /admin/requests → 200.
2. HTML에 '접수 목록', 시작일/종료일/사업소/상태 label, 테이블 헤더,
   엑셀 다운로드 링크, 상세 링크 존재.
3. role="status", aria-live="polite" 존재.
4. seed 접수 1건이 접수번호·상태 텍스트(badge)·전체수량으로 렌더링.
5. 빈 목록(매칭 없는 필터)에서 empty state 표시.
6. 필터 query를 붙여도 200이고 선택값(value/selected) 유지.
7. /static/css/app.css 와 /static/css/wanted.css 연결.
8. 기존 API 회귀는 전체 테스트(uv run pytest tests/ -q)로 확인;
   본 파일은 GET /api/requests 스모크만 포함.

방식: 임시 SQLite(in-memory, StaticPool) + TestClient.
- 목록 화면(_list_rows/_office_choices)은 get_db가 아닌
  server 모듈 전역 SessionLocal 을 직접 사용하므로
  server_module.SessionLocal / engine 을 임시 DB로 monkeypatch.
- API 스모크용 get_db 의존성은 dependency_overrides 로 임시 세션 대체.
"""

import re
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
from app.main.api.requests import get_db
import app.server as server_module
from app.server import app


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def seeded_db():
    """임시 in-memory SQLite 에 사업소 1건 + 접수 1건(RECEIVED) 시딩.

    StaticPool 단일 연결 공유 → 목록 화면과 API가 같은 DB 참조.
    """
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

    req = RequestModel(
        request_no="R-20260901-0101",
        business_office_id=office.id,
        pickup_date=date(2026, 9, 1),
        pickup_location_type=PickupLocationType.HOME,  # "자택"
        pickup_address="서울시 강남구 테헤란로 123",
        current_status=RequestStatus.RECEIVED,
        electric_bed_quantity=1,
        wheelchair_quantity=2,
        other_small_quantity=0,
        created_at=now,
        updated_at=now,
    )
    db.add(req)
    db.commit()

    yield {
        "session": db,
        "factory": factory,
        "engine": engine,
        "office_id": office.id,
        "office_name": office.name,
        "request_id": req.id,
        "request_no": req.request_no,
        "total_qty": 1 + 2 + 0,
    }
    db.close()
    engine.dispose()


@pytest.fixture
def client(seeded_db, monkeypatch):
    """목록 화면 + API 가 모두 임시 DB 를 쓰도록 연결.

    - server_module.SessionLocal / engine = 임시 DB
      (목록 화면이 직접 사용하는 전역 참조를 교체)
    - get_db 의존성 = 임시 세션 (API 스모크용)
    """

    def override_get_db():
        s = seeded_db["factory"]()
        try:
            yield s
        finally:
            s.close()

    monkeypatch.setattr(server_module, "SessionLocal", seeded_db["factory"])
    monkeypatch.setattr(server_module, "engine", seeded_db["engine"])
    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as c:
        yield c
    app.dependency_overrides.pop(get_db, None)


def _assert_has(html: str, needle: str, label: str):
    assert needle in html, f"{label} not found: {needle!r}"


# ---------------------------------------------------------------------------
# 1-3. 페이지 렌더링 + 접근성
# ---------------------------------------------------------------------------
class TestListPageRenders:
    def test_get_returns_200(self, client):
        resp = client.get("/admin/requests")
        assert resp.status_code == 200, resp.text
        assert "<html" in resp.text.lower()

    def test_page_title(self, client):
        html = client.get("/admin/requests").text
        _assert_has(html, "접수 목록", "page title")

    def test_live_status_role_and_aria(self, client):
        html = client.get("/admin/requests").text
        _assert_has(html, 'role="status"', "role=status")
        _assert_has(html, 'aria-live="polite"', "aria-live=polite")
        # 목록 전용 live region
        _assert_has(html, 'id="list-status"', "list-status region")


# ---------------------------------------------------------------------------
# 2. 필터 컨트롤 + 테이블 헤더 + 링크
# ---------------------------------------------------------------------------
class TestFilterControls:
    def test_filter_labels(self, client):
        html = client.get("/admin/requests").text
        for label in ("시작일", "종료일", "사업소", "상태"):
            _assert_has(html, label, f"label {label}")

    def test_filter_inputs(self, client):
        html = client.get("/admin/requests").text
        _assert_has(html, 'name="pickup_date_from"', "pickup_date_from input")
        _assert_has(html, 'name="pickup_date_to"', "pickup_date_to input")
        _assert_has(html, 'name="business_office_id"', "business_office_id select")
        _assert_has(html, 'name="current_status"', "current_status select")

    def test_table_headers(self, client):
        html = client.get("/admin/requests").text
        for header in ("접수번호", "사업소", "수거 희망일", "상태", "전체 수량"):
            _assert_has(html, header, f"table header {header}")

    def test_excel_download_link(self, client):
        html = client.get("/admin/requests").text
        _assert_has(html, "/api/requests/export", "excel export link")
        _assert_has(html, "엑셀 다운로드", "excel link text")

    def test_detail_link_present(self, client, seeded_db):
        html = client.get("/admin/requests").text
        link = f"/admin/requests/{seeded_db['request_id']}"
        _assert_has(html, link, "detail link")
        _assert_has(html, "상세 보기", "detail link text")


# ---------------------------------------------------------------------------
# 4. seed 데이터 렌더링
# ---------------------------------------------------------------------------
class TestSeedRendered:
    def test_request_no_rendered(self, client, seeded_db):
        html = client.get("/admin/requests").text
        _assert_has(html, seeded_db["request_no"], "request_no")

    def test_status_badge_rendered(self, client):
        html = client.get("/admin/requests").text
        # 상태 텍스트는 색상과 병기된 badge 로 렌더링 (색상 단독 금지)
        _assert_has(html, "status-badge status-received", "status badge class")
        _assert_has(html, "접수", "status text RECEIVED")

    def test_office_name_rendered(self, client, seeded_db):
        html = client.get("/admin/requests").text
        _assert_has(html, seeded_db["office_name"], "office name")

    def test_total_qty_rendered(self, client, seeded_db):
        html = client.get("/admin/requests").text
        qty = str(seeded_db["total_qty"])
        pattern = rf'class="req-qty">{qty}<'
        assert re.search(pattern, html), f"total_qty cell {qty} not rendered"


# ---------------------------------------------------------------------------
# 5. empty state
# ---------------------------------------------------------------------------
class TestEmptyState:
    def test_empty_state_shown_for_non_matching_filter(self, client):
        # 시드는 RECEIVED 이므로 DELIVERED 필터 → 0건 → empty state
        resp = client.get("/admin/requests", params={"current_status": "DELIVERED"})
        assert resp.status_code == 200, resp.text
        html = resp.text
        _assert_has(html, "empty-state", "empty state block")
        _assert_has(html, "표시할 접수가 없습니다.", "empty state text")
        # 데이터 행(접수번호)은 렌더링되지 않음
        assert "R-20260901-0101" not in html, "seed row should be filtered out"

    def test_no_empty_state_when_rows_exist(self, client):
        html = client.get("/admin/requests").text
        assert "empty-state" not in html, "empty state should not show with data"


# ---------------------------------------------------------------------------
# 6. 필터 query → 200 + 선택값 유지
# ---------------------------------------------------------------------------
class TestFilterRetained:
    def test_filter_query_returns_200(self, client):
        resp = client.get(
            "/admin/requests",
            params={
                "pickup_date_from": "2026-09-01",
                "pickup_date_to": "2026-09-30",
                "current_status": "RECEIVED",
            },
        )
        assert resp.status_code == 200, resp.text

    def test_date_values_retained(self, client):
        html = client.get(
            "/admin/requests",
            params={"pickup_date_from": "2026-09-01", "pickup_date_to": "2026-09-30"},
        ).text
        _assert_has(html, 'value="2026-09-01"', "from date value")
        _assert_has(html, 'value="2026-09-30"', "to date value")

    def test_status_select_selected(self, client):
        html = client.get(
            "/admin/requests", params={"current_status": "RECEIVED"}
        ).text
        # RECEIVED option 에 selected 속성
        pattern = r'<option value="RECEIVED"[^>]*selected'
        assert re.search(pattern, html), "RECEIVED option not marked selected"

    def test_office_select_selected(self, client, seeded_db):
        html = client.get(
            "/admin/requests", params={"business_office_id": seeded_db["office_id"]}
        ).text
        pattern = (
            rf'<option value="{seeded_db["office_id"]}"[^>]*selected'
        )
        assert re.search(pattern, html), "selected office option missing"


# ---------------------------------------------------------------------------
# 7. 정적 리소스 연결
# ---------------------------------------------------------------------------
class TestStaticAssets:
    def test_css_links_in_html(self, client):
        html = client.get("/admin/requests").text
        _assert_has(html, "/static/css/wanted.css", "wanted.css link")
        _assert_has(html, "/static/css/app.css", "app.css link")

    def test_wanted_css_served(self, client):
        r = client.get("/static/css/wanted.css")
        assert r.status_code == 200

    def test_app_css_served(self, client):
        r = client.get("/static/css/app.css")
        assert r.status_code == 200


# ---------------------------------------------------------------------------
# 8. 기존 API 회귀 (스모크; 상세 회귀는 전체 스위트에서 확인)
# ---------------------------------------------------------------------------
class TestApiSmoke:
    def test_list_api_still_works(self, client, seeded_db):
        r = client.get("/api/requests")
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["total"] >= 1
        nos = [it["request_no"] for it in body["items"]]
        assert seeded_db["request_no"] in nos
