"""WP-09 소독완료 이후 PDF 다운로드 흐름 테스트.

- 임시 SQLite(in-memory) + StaticPool 단일 연결 + TestClient + get_db 오버라이드
- 사업소 2개 + 카운터 시딩, 접수 4건: RECEIVED / PICKED_UP / DISINFECTED / DELIVERED
- API 생성 PDF 는 tmp_path 로 리다이렉트 (실제 runtime/pdf 오염 금지)
- 프로토타입 표시 검증: generate_request_pdf 직접 호출 결과 파일 기준
"""

import re

import pytest
from datetime import date, datetime, timezone, timedelta
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import pool

from app.main.db.base import Base
from app.main.models.models import BusinessOffice, Request, RequestNoCounter
from app.main.api import requests as api_module
from app.main.api.requests import get_db
from app.main.services.pdf_service import PROTOTYPE_NOTICE, _status_label, generate_request_pdf
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


@pytest.fixture
def pdf_dir(tmp_path, monkeypatch):
    """API 경로를 통한 PDF 생성을 tmp_path 로 리다이렉트.

    실제 runtime/pdf/ 디렉터리에 파일이 남지 않도록 한다.
    """
    real = api_module.generate_request_pdf

    def fake(request):
        return real(request, out_dir=tmp_path)

    monkeypatch.setattr(api_module, "generate_request_pdf", fake)
    return tmp_path


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


D1 = (date.today() + timedelta(days=7)).isoformat()
D2 = (date.today() + timedelta(days=8)).isoformat()
D3 = (date.today() + timedelta(days=9)).isoformat()
D4 = (date.today() + timedelta(days=10)).isoformat()


@pytest.fixture
def seeded(client):
    """접수 4건 시딩 + 상태 전이.

    r1: RECEIVED / r2: PICKED_UP / r3: DISINFECTED / r4: DELIVERED
    """
    ids = {}
    specs = (("r1", 1, D1), ("r2", 1, D2), ("r3", 2, D3), ("r4", 2, D4))
    for i, (key, office, d) in enumerate(specs, start=1):
        r = client.post("/api/requests", json=_payload(office, d, i))
        assert r.status_code == 201, r.text
        ids[key] = r.json()["id"]

    r = client.patch(f"/api/requests/{ids['r2']}/status", json={"target_status": "PICKED_UP"})
    assert r.status_code == 200, r.text

    for key in ("r3", "r4"):
        r = client.patch(f"/api/requests/{ids[key]}/status", json={"target_status": "PICKED_UP"})
        assert r.status_code == 200, r.text

    r = client.patch(f"/api/requests/{ids['r3']}/status", json={"target_status": "DISINFECTED"})
    assert r.status_code == 200, r.text
    r = client.patch(f"/api/requests/{ids['r4']}/status", json={"target_status": "DISINFECTED"})
    assert r.status_code == 200, r.text
    r = client.patch(f"/api/requests/{ids['r4']}/status", json={"target_status": "DELIVERED"})
    assert r.status_code == 200, r.text

    return ids


def _unescapew_pdf_bytes(data: bytes) -> bytes:
    """PDF 문자열 리터럴 이스케이프를 원본 바이트로 복원.

    PDF 파일 바이트에서 \\\\ooo(8진) 이스케이프와 \\\\  \\\\  \\\\) 를
    실제 바이트값으로 되돌려 프로토타입 표시(UTF-16BE)를 검색 가능하게 한다.
    """
    out = bytearray()
    i = 0
    n = len(data)
    while i < n:
        ch = data[i]
        if ch == 0x5C and i + 1 < n:  # backslash
            nxt = data[i + 1]
            if 0x30 <= nxt <= 0x37:  # '0'..'7' → octal escape
                m = re.match(rb"\\([0-7]{1,3})", data[i:i + 4])
                if m:
                    out.append(int(m.group(1), 8))
                    i += m.end()
                    continue
            elif nxt in (0x5C, 0x28, 0x29):  # \\  (  )
                out.append(nxt)
                i += 2
                continue
        out.append(ch)
        i += 1
    return bytes(out)


class TestPdfDeniedBeforeDisinfected:
    """1-2. 소독완료 이전 상태는 PDF 거부 (409)"""

    def test_received_denied(self, client, seeded, pdf_dir):
        r = client.get(f"/api/requests/{seeded['r1']}/pdf")
        assert r.status_code == 409, r.text
        assert "RECEIVED" in r.json()["detail"]

    def test_picked_up_denied(self, client, seeded, pdf_dir):
        r = client.get(f"/api/requests/{seeded['r2']}/pdf")
        assert r.status_code == 409, r.text
        assert "PICKED_UP" in r.json()["detail"]


class TestPdfDownload:
    """3-4. DISINFECTED / DELIVERED 는 200 + application/pdf + 유효 PDF"""

    def test_disinfected_pdf_200(self, client, seeded, pdf_dir):
        r = client.get(f"/api/requests/{seeded['r3']}/pdf")
        assert r.status_code == 200, r.text
        assert r.headers["content-type"] == "application/pdf"
        assert r.content.startswith(b"%PDF")
        assert len(r.content) > 0

    def test_delivered_pdf_200(self, client, seeded, pdf_dir):
        r = client.get(f"/api/requests/{seeded['r4']}/pdf")
        assert r.status_code == 200, r.text
        assert r.headers["content-type"] == "application/pdf"
        assert r.content.startswith(b"%PDF")
        assert len(r.content) > 0

    def test_pdf_written_to_injected_dir_not_runtime(self, client, seeded, pdf_dir):
        """API 생성 PDF 는 주입된 tmp 디렉터리에만 생성된다."""
        r = client.get(f"/api/requests/{seeded['r3']}/pdf")
        assert r.status_code == 200, r.text
        files = list(pdf_dir.glob("*.pdf"))
        assert len(files) == 1
        assert files[0].stat().st_size > 0
        assert files[0].name.startswith("R-")


class TestPdfNotFound:
    """5. 미존재 id 404"""

    def test_not_found_404(self, client, seeded, pdf_dir):
        r = client.get("/api/requests/99999/pdf")
        assert r.status_code == 404, r.text
        assert "존재하지 않는 접수" in r.json()["detail"]


class TestPdfContent:
    """6. PDF 응답/파일에 프로토타입 표시 검증 (생성 함수 결과 기준)"""

    def test_service_output_has_notice_and_meta(self, test_db, seeded, tmp_path):
        req = test_db.get(Request, seeded["r3"])
        path = generate_request_pdf(req, out_dir=tmp_path)

        assert path.is_file()
        assert path.parent == tmp_path
        assert path.name == f"{req.request_no}.pdf"

        data = path.read_bytes()
        assert data.startswith(b"%PDF")
        assert len(data) > 0

        # /Title 메타데이터에 notice 가 UTF-16BE(+BOM) 로 기록됨 (PDF 이스케이프 복원 후 검색)
        restored = _unescapew_pdf_bytes(data)
        assert PROTOTYPE_NOTICE.encode("utf-16-be") in restored
        # 접수번호도 문서에 포함 (Title 이 아닌 본문은 CID 인코딩 → Title/메타 기준 외
        # ASCII 접수번호는 콘텐츠 스트림에 그대로 존재)
        assert req.request_no.encode("ascii") in data
        assert _status_label(req.current_status) == "소독완료"
        assert b"DISINFECTED" not in data

    def test_notice_constant_value(self):
        assert PROTOTYPE_NOTICE == "기술 프로토타입 - 공단 제출용 아님"


class TestExistingApisRegression:
    """7. 기존 POST/PATCH 수정/status/query API 회귀"""

    def test_post_create_still_works(self, client, seeded, pdf_dir):
        r = client.post("/api/requests", json=_payload(1, D4, 99))
        assert r.status_code == 201, r.text
        assert r.json()["current_status"] == "RECEIVED"

    def test_patch_update_still_works(self, client, seeded, pdf_dir):
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

    def test_status_api_still_works(self, client, seeded, pdf_dir):
        r = client.post("/api/requests", json=_payload(2, D4, 98))
        assert r.status_code == 201, r.text
        rid = r.json()["id"]
        r = client.patch(f"/api/requests/{rid}/status", json={"target_status": "PICKED_UP"})
        assert r.status_code == 200, r.text
        assert r.json()["current_status"] == "PICKED_UP"

    def test_list_api_still_works(self, client, seeded, pdf_dir):
        r = client.get("/api/requests")
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["total"] == 4
        assert len(body["items"]) == 4
