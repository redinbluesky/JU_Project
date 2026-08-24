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
    RequestStatusHistory,
)
from app.main.services.request_service import get_request

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

NEXT_STATUS = {
    RequestStatus.RECEIVED: RequestStatus.PICKED_UP,
    RequestStatus.PICKED_UP: RequestStatus.DISINFECTED,
    RequestStatus.DISINFECTED: RequestStatus.DELIVERED,
}


def _office_choices() -> list[dict]:
    """사업소 select 옵션 (DB 조회, 실패 시 빈 목록)."""
    try:
        with SessionLocal() as db:
            rows = db.query(BusinessOffice).order_by(BusinessOffice.id).all()
            return [{"id": r.id, "code": r.code, "name": r.name} for r in rows]
    except Exception:
        return []


def _list_rows(pickup_from=None, pickup_to=None, office_id=None, status=None):
    """목록 화면 렌더링 데이터 (기존 list_requests 서비스 재사용)."""
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
                    "total_qty": r.electric_bed_quantity + r.wheelchair_quantity + r.other_small_quantity,
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
    """접수 목록 페이지 (WP-14-B2A)."""
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
            "pickup_date_from": pickup_date_from or "",
            "pickup_date_to": pickup_date_to or "",
            "business_office_id": business_office_id or "",
            "current_status": current_status or "",
            "has_filters": bool(pickup_date_from or pickup_date_to or business_office_id or current_status),
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


@app.get("/admin/requests/{request_id}", name="admin_request_detail")
def admin_request_detail(request: Request, request_id: int):
    """접수 상세 화면 (WP-14-B2B)."""
    with SessionLocal() as db:
        item = get_request(db, request_id)
        if item is None:
            return templates.TemplateResponse(
                request,
                "requests/notfound.html",
                {"request_id": request_id},
                status_code=404,
            )
        office = db.get(BusinessOffice, item.business_office_id)
        histories = (
            db.query(RequestStatusHistory)
            .filter(RequestStatusHistory.request_id == request_id)
            .order_by(RequestStatusHistory.sequence.asc())
            .all()
        )
        status = item.current_status
        next_status = NEXT_STATUS.get(status)
        detail = {
            "id": item.id,
            "request_no": item.request_no,
            "office_name": office.name if office else f"사업소#{item.business_office_id}",
            "pickup_date": item.pickup_date,
            "pickup_location_type": item.pickup_location_type.value,
            "pickup_address": item.pickup_address,
            "electric_bed_quantity": item.electric_bed_quantity,
            "wheelchair_quantity": item.wheelchair_quantity,
            "other_small_quantity": item.other_small_quantity,
            "total_quantity": item.electric_bed_quantity + item.wheelchair_quantity + item.other_small_quantity,
            "status": status.value,
            "status_label": STATUS_LABELS[status.value],
            "created_at": item.created_at,
            "updated_at": item.updated_at,
            "completion_date": item.completion_date,
            "histories": [
                {
                    "sequence": h.sequence,
                    "status": h.status.value,
                    "status_label": STATUS_LABELS[h.status.value],
                    "changed_at": h.changed_at,
                }
                for h in histories
            ],
            "next_status": next_status.value if next_status else None,
            "next_status_label": STATUS_LABELS[next_status.value] if next_status else None,
            "can_edit": status is RequestStatus.RECEIVED,
            "can_download_pdf": status in (RequestStatus.DISINFECTED, RequestStatus.DELIVERED),
        }
    return templates.TemplateResponse(request, "requests/detail.html", {"item": detail})


@app.get("/health")
def health_check():
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"status": "ok", "db": "connected"}
    except Exception as e:
        return {"status": "error", "db": str(e)}
