"""Request API 라우터"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError
from app.main.db.session import SessionLocal
from app.main.models.models import Request, RequestStatus, RequestStatusHistory
from app.main.schemas.request import (
    RequestCreate,
    RequestUpdate,
    RequestOut,
    RequestStatusTransition,
)
from app.main.services.request_service import (
    create_request,
    update_request,
    transition_request_status,
)

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


@router.patch("/{request_id}", response_model=RequestOut)
def patch_request(request_id: int, data: RequestUpdate, db: Session = Depends(get_db)):
    """RECEIVED 상태 접수 수정 (200 성공, ValueError → 409, 그 외 → 500)"""
    try:
        request = update_request(db, request_id, data)
        return request
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"접수 수정 실패: {str(e)}",
        )


@router.patch("/{request_id}/status", response_model=RequestOut)
def patch_request_status(
    request_id: int,
    data: RequestStatusTransition,
    db: Session = Depends(get_db),
):
    """상태 전이 (바로 다음 상태만 허용).

    성공 200 / ValueError(불법 전이·미존재·중복) 409 /
    StaleDataError(동시 수정 충돌) 409 / 그 외 예외 rollback 후 500.
    """
    try:
        request = transition_request_status(db, request_id, data.target_status)
        return request
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except StaleDataError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="다른 요청이 먼저 변경했으므로 다시 조회 후 재시도해 주세요.",
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"상태 변경 실패: {str(e)}",
        )