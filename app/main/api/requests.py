"""Request API 라우터"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.main.db.session import SessionLocal
from app.main.models.models import Request, RequestStatusHistory
from app.main.schemas.request import RequestCreate, RequestOut
from app.main.services.request_service import create_request

router = APIRouter(prefix="/api/requests", tags=["requests"])


def get_db():
    """DB 세션 의존성"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("", response_model=RequestOut, status_code=status.HTTP_201_CREATED)
def create_new_request(data: RequestCreate, db: Session = Depends(get_db)):
    """새 접수 생성"""
    try:
        request = create_request(db, data)
        return request
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"접수 생성 실패: {str(e)}",
        )
