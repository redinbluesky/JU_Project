"""WP-11 목록 필터 결과 엑셀 다운로드 서비스.

openpyxl 로 XLSX 를 생성한다.

- 디폴트 출력: 프로젝트 루트 runtime/xlsx/ (개발 실행 시 실제 파일 생성 위치)
- 테스트는 generate_requests_xlsx(db, filters, out_dir=tmp_path) 로 출력
  경로를 주입해 실제 runtime/ 를 오염시키지 않는다.
- 행 집합·정렬은 목록 API 와 동일: list_requests() 를 그대로 재사용
  (pickup_date ASC, id ASC).
- 필수 10개 열(고정 순서):
  접수번호 / 사업소 / 수거 희망일 / 수거 장소 유형 / 수거 주소 /
  전동침대 수량 / 휠체어 수량 / 기타 소형 용구 수량 / 상태 / 완료일
- 사업소는 BusinessOffice.name 으로 표시 (id 아님).
- 상태는 RequestStatus.value.
- 날짜는 ISO (YYYY-MM-DD) 문자열. 완료일 미설정 시 빈 문자열.
- 사용자 입력 문자열(주소 등)에는 sanitize_excel_cell() 을 적용해
  =, +, -, @ 시작 값이 엑셀 수식으로 해석되지 않게 한다.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

from openpyxl import Workbook
from sqlalchemy.orm import Session

from app.main.models.models import BusinessOffice, Request
from app.main.services.excel_utils import sanitize_excel_cell
from app.main.services.request_service import list_requests

# 필수 10개 열 (표시 순서 고정)
COLUMNS = [
    "접수번호",
    "사업소",
    "수거 희망일",
    "수거 장소 유형",
    "수거 주소",
    "전동침대 수량",
    "휠체어 수량",
    "기타 소형 용구 수량",
    "상태",
    "완료일",
]


def _project_root() -> Path:
    """프로젝트 루트: app/main/services/excel_service.py → 상위 3단계."""
    return Path(__file__).resolve().parents[3]


def _default_xlsx_dir() -> Path:
    """개발 실행 디폴트 엑셀 출력 디렉터리: runtime/xlsx/."""
    return _project_root() / "runtime" / "xlsx"


def _enum_value(value):
    """enum 인스턴스든 문자열이든 표시값(.value)으로 정규화."""
    return value.value if hasattr(value, "value") else value


def _cell(value):
    """셀 값: 문자열은 수식 인젝션 방지 sanitize 적용, 그 외(숫자 등)는 그대로."""
    if isinstance(value, str):
        return sanitize_excel_cell(value)
    return value


def _iso(value) -> str:
    """date/datetime → ISO 문자열, 미설정 → 빈 문자열."""
    return value.isoformat() if value is not None else ""


def generate_requests_xlsx(
    db: Session,
    filters: dict | None = None,
    out_dir: Path | str | None = None,
) -> Path:
    """현재 목록 필터 결과를 XLSX 로 생성해 파일 경로를 반환한다.

    filters 키 (모두 임의):
        pickup_date_from (date) — 수거희망일 시작 (포함)
        pickup_date_to (date)   — 수거희망일 끝 (포함)
        business_office_id (int)
        current_status (RequestStatus)
    (from > to 검증은 호출부(API)가 422 로 거부)

    - out_dir 지정 시 그 디렉터리, 미지정 시 runtime/xlsx/
    - 행 집합·정렬은 list_requests() 재사용 (목록 API 와 동일)
    - 헤더(10개 열)는 항상 첫 행. 0건이어도 헤더만 가진 유효한 XLSX.
    """
    out = Path(out_dir) if out_dir is not None else _default_xlsx_dir()
    out.mkdir(parents=True, exist_ok=True)
    fname = datetime.now(timezone.utc).strftime("requests_export_%Y%m%d_%H%M%S.xlsx")
    path = out / fname

    rows = list_requests(
        db,
        pickup_date_from=(filters or {}).get("pickup_date_from"),
        pickup_date_to=(filters or {}).get("pickup_date_to"),
        business_office_id=(filters or {}).get("business_office_id"),
        current_status=(filters or {}).get("current_status"),
    )

    wb = Workbook()
    ws = wb.active
    ws.title = "접수목록"
    ws.append(COLUMNS)

    office_names: dict[int, str] = {}

    def _office_name(office_id: int) -> str:
        if office_id not in office_names:
            office = db.get(BusinessOffice, office_id)
            office_names[office_id] = office.name if office is not None else str(office_id)
        return office_names[office_id]

    for req in rows:
        row = [
            req.request_no,
            _office_name(req.business_office_id),
            _iso(req.pickup_date),
            _enum_value(req.pickup_location_type),
            req.pickup_address,
            req.electric_bed_quantity,
            req.wheelchair_quantity,
            req.other_small_quantity,
            _enum_value(req.current_status),
            _iso(req.completion_date),
        ]
        ws.append([_cell(v) for v in row])

    wb.save(str(path))
    return path
