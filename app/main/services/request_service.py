"""Request 생성 서비스"""

from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import datetime, timezone
from app.main.models.models import Request, RequestStatus, RequestStatusHistory, PickupLocationType
from app.main.schemas.request import RequestCreate


def _get_next_request_no(db: Session) -> str:
    """RequestNoCounter 테이블에서 다음 접수번호를 생성 (RETURNING + 폴백)"""
    try:
        # SQLite 3.35+ UPDATE ... RETURNING 시도
        result = db.execute(
            text("""
                UPDATE request_no_counter
                SET current_value = current_value + 1
                WHERE id = 1
                RETURNING current_value
            """)
        )
        next_value = result.scalar_one()
    except Exception:
        # 폴백: UPDATE 후 SELECT
        db.execute(
            text("""
                UPDATE request_no_counter
                SET current_value = current_value + 1
                WHERE id = 1
            """)
        )
        result = db.execute(text("SELECT current_value FROM request_no_counter WHERE id = 1"))
        next_value = result.scalar_one()

    return f"R-{next_value:010d}"


def create_request(db: Session, data: RequestCreate) -> Request:
    """Request 생성 - RequestNoCounter 테이블 기반 채번"""
    now = datetime.now(timezone.utc)

    # 카운터 테이블에서 다음 번호 획득 (트랜잭션 내)
    request_no = _get_next_request_no(db)

    # PickupLocationType Enum으로 변환
    location_type = PickupLocationType(data.pickup_location_type)

    request = Request(
        request_no=request_no,
        business_office_id=data.business_office_id,
        pickup_date=data.pickup_date,
        pickup_location_type=location_type,
        pickup_address=data.pickup_address,
        current_status=RequestStatus.RECEIVED,
        electric_bed_quantity=data.electric_bed_quantity,
        wheelchair_quantity=data.wheelchair_quantity,
        other_small_quantity=data.other_small_quantity,
        created_at=now,
        updated_at=now,
    )

    db.add(request)
    db.flush()

    # 상태 이력 생성
    history = RequestStatusHistory(
        request_id=request.id,
        status=RequestStatus.RECEIVED,
        changed_at=now,
        sequence=1,
    )
    db.add(history)
    db.commit()

    return request
