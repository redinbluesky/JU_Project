from datetime import date, timedelta
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import text

from app.main.api.requests import router
from app.main.db.session import SessionLocal, engine
from app.main.models.models import (
    BusinessOffice,
    Request as RequestModel,
    RequestStatus,
)

app = FastAPI(title="JU Prototype", version="0.1.0")

app.include_router(router)

# 정적 리소스(/static/**)와 Jinja2 템플릿 배선.
BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

# 상태 라벨 (색상 단독 금지: 항상 텍스트와 병기)
STATUS_LABELS = {
    "RECEIVED": "접수",
    "PICKED_UP": "수거완료",
    "DISINFECTED": "소독완료",
    "DELIVERED": "배달완료",
}


def _office_choices() -> list[dict]:
    """사업소 select 옵션 (DB 조회, 실패 시 빈 목록)."""
    try:
        with SessionLocal() as db:
            rows = (
                db.query(BusinessOffice)
                .order_by(BusinessOffice.id)
                .all()
            )
            return [
                {"id": r.id, "code": r.code, "name": r.name}
                for r in rows
            ]
    except Exception:
        return []


def _list_rows(pickup_from=None, pickup_to=None, office_id=None, status=None):
    """목록 화면 렌더링 데이터 (기존 list_requests 서비스 재사용).

    - 기간: pickup_date >= from / <= to
    - 정렬: pickup_date ASC, id ASC (API와 동일)
    - 실패 시 빈 목록 (화면은 empty state로 안전하게 표시)
    """
    try:
        with SessionLocal() as db:
            q = db.query(RequestModel)
            if pickup_from is not None:
                q = q.filter(RequestModel.pickup_date >= date.fromisoformat(pickup_from))
            if pickup_to is not None:
                q = q.filter(RequestModel.pickup_date <= date.fromisoformat(pickup_to))
            if office_id is not None:
                q = q.filter(RequestModel.business_office_id == int(office_id))
            if status is not None and status in STATUS_LABELS:
                q = q.filter(RequestModel.current_status == status)
            rows = q.order_by(RequestModel.pickup_date, RequestModel.id).all()
            offices = {o.id: o.name for o in db.query(BusinessOffice).all()}
            return [
                {
                    "id": r.id,
                    "request_no": r.request_no,
                    "office_name": offices.get(r.business_office_id, f"사업소#{r.business_office_id}"),
                    "pickup_date": r.pickup_date.isoformat(),
                    "status": r.current_status.value,
                    "status_label": STATUS_LABELS[r.current_status.value],
                    "total_qty": (
                        r.electric_bed_quantity
                        + r.wheelchair_quantity
                        + r.other_small_quantity
                    ),
                }
                for r in rows
            ]
    except Exception:
        return []


@app.get("/requests/new", name="request_new")
def request_new_page(request: Request):
    """신규 접수 페이지 (WP-14-B1)."""
    return templates.TemplateResponse(
        request,
        "requests/new.html",
        {
            "offices": _office_choices(),
            # API 검증: 수거희망일은 오늘 이후만 허용 → 오늘 다음 날이 최소값.
            "pickup_min": (date.today() + timedelta(days=1)).isoformat(),
        },
    )


@app.get("/admin/requests", name="admin_requests_list")
def admin_requests_list(
    request: Request,
    pickup_date_from: str | None = None,
    pickup_date_to: str | None = None,
    business_office_id: int | None = None,
    current_status: str | None = None,
):
    """접수 목록 페이지 (WP-14-B2A).

    서버 측 초기 렌더링: 같은 필터로 DB 조회 → 행을 Jinja2 템플릿에 넘긴다.
    필터 파라미터는 그대로 쿼리스트링에 반영되어 재사용된다(링크/리프레시 안전).
    """
    rows = _list_rows(
        pickup_from=pickup_date_from,
        pickup_to=pickup_date_to,
        office_id=business_office_id,
        status=current_status,
    )
    return templates.TemplateResponse(
        request,
        "requests/list.html",
        {
            "rows": rows,
            "offices": _office_choices(),
            "status_labels": STATUS_LABELS,
            # 서버 렌더 기준 필터 값(빈 값은 None → input value 비어감)
            "pickup_date_from": pickup_date_from or "",
            "pickup_date_to": pickup_date_to or "",
            "business_office_id": business_office_id or "",
            "current_status": current_status or "",
            # 필터가 적용되어 있는지(엑셀 링크에 같은 쿼리 붙이기용)
            "has_filters": bool(
                pickup_date_from or pickup_date_to or business_office_id or current_status
            ),
            "export_url": _export_url(pickup_date_from, pickup_date_to, business_office_id, current_status),
        },
    )


def _export_url(pickup_date_from, pickup_date_to, office_id, status) -> str:
    """현재 필터와 동일한 조건의 엑셀 다운로드 링크."""
    params = []
    if pickup_date_from:
        params.append(f"pickup_date_from={pickup_date_from}")
    if pickup_date_to:
        params.append(f"pickup_date_to={pickup_date_to}")
    if office_id is not None:
        params.append(f"business_office_id={office_id}")
    if status:
        params.append(f"current_status={status}")
    return "/api/requests/export" + ("?" + "&".join(params) if params else "")


@app.get("/health")
def health_check():
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"status": "ok", "db": "connected"}
    except Exception as e:
        return {"status": "error", "db": str(e)}
