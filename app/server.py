from datetime import date, timedelta
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import text

from app.main.api.requests import router
from app.main.db.session import SessionLocal, engine
from app.main.models.models import BusinessOffice

app = FastAPI(title="JU Prototype", version="0.1.0")

app.include_router(router)

# WP-14-B1: 정적 리소스(/static/**)와 Jinja2 템플릿 배선.
BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")


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


@app.get("/health")
def health_check():
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"status": "ok", "db": "connected"}
    except Exception as e:
        return {"status": "error", "db": str(e)}
