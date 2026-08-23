"""Request 생성/수정 서비스"""

from sqlalchemy.orm import Session
from sqlalchemy import text, select, func
from datetime import datetime, timezone
from app.main.models.models import Request, RequestStatus, RequestStatusHistory, PickupLocationType
from app.main.schemas.request import RequestCreate, RequestUpdate


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


def update_request(db: Session, request_id: int, data: RequestUpdate) -> Request:
    """수정 - RECEIVED 상태의 접수만 수정 가능.

    실패 시 ValueError:
      - 접수 미존재
      - 현재 상태가 RECEIVED가 아닌 경우
    """
    request = db.get(Request, request_id)
    if request is None:
        raise ValueError(f"존재하지 않는 접수: id={request_id}")
    if request.current_status != RequestStatus.RECEIVED:
        raise ValueError(
            f"수정 불가: 현재 상태는 {request.current_status} (수정 가능 상태는 RECEIVED만 허용)"
        )

    # 수정 가능 필드만 갱신 (business_office_id는 수정 불가)
    request.pickup_date = data.pickup_date
    request.pickup_location_type = data.pickup_location_type
    request.pickup_address = data.pickup_address
    request.electric_bed_quantity = data.electric_bed_quantity
    request.wheelchair_quantity = data.wheelchair_quantity
    request.other_small_quantity = data.other_small_quantity
    request.updated_at = datetime.now(timezone.utc)

    db.commit()
    return request


# 상태 전이 맵: 현재 상태 -> 허용되는 바로 다음 상태
ALLOWED_TRANSITIONS: dict[RequestStatus, RequestStatus] = {
    RequestStatus.RECEIVED: RequestStatus.PICKED_UP,
    RequestStatus.PICKED_UP: RequestStatus.DISINFECTED,
    RequestStatus.DISINFECTED: RequestStatus.DELIVERED,
    # DELIVERED는 종결 상태 (다음 없음)
}


def transition_request_status(db: Session, request_id: int, target_status: RequestStatus) -> Request:
    """상태 전이 도메인 서비스.

    승인된 전이(바로 다음 상태만):
        RECEIVED -> PICKED_UP -> DISINFECTED -> DELIVERED

    위반 시 ValueError:
      - 접수 미존재
      - 건너뛰기 / 역방향 / 동일 상태 중복 / DELIVERED 이후 전이

    규칙:
      - 현재 상태 변경과 이력 추가를 하나의 db.commit()으로 처리
      - sequence = 현재 이력 최대값 + 1
      - DELIVERED 이면 completion_date = 현재 UTC 날짜
      - 검증은 commit 전에 끝내고 실패 시 롤백(상태·이력 불변)
    """
    request = db.get(Request, request_id)
    if request is None:
        raise ValueError(f"존재하지 않는 접수: id={request_id}")

    current = request.current_status
    allowed_next = ALLOWED_TRANSITIONS.get(current)
    if target_status is not allowed_next:
        raise ValueError(
            f"허용되지 않은 상태 전이: {current.value} -> {target_status.value} (바로 다음 상태만 허용)"
        )

    now = datetime.now(timezone.utc)

    # 다음 sequence 계산 (현재 이력 최대값 + 1)
    max_seq_row = db.execute(
        select(func.max(RequestStatusHistory.sequence)).where(
            RequestStatusHistory.request_id == request_id
        )
    ).scalar_one()
    next_sequence = (max_seq_row or 0) + 1

    # 이력 추가
    db.add(
        RequestStatusHistory(
            request_id=request_id,
            status=target_status,
            changed_at=now,
            sequence=next_sequence,
        )
    )

    # 현재 상태 변경
    request.current_status = target_status

    # DELIVERED 이면 완료 날짜 기록 (현재 UTC 날짜)
    if target_status is RequestStatus.DELIVERED:
        request.completion_date = now.date()

    request.updated_at = now

    # 상태 변경 + 이력 추가를 하나의 커밋으로 처리
    db.commit()
    return request
