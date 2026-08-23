"""Request 생성/수정 서비스"""

from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError
from sqlalchemy import text, select, func
from datetime import date, datetime, timezone
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

    # 상태 변경 + 이력 추가를 하나의 커밋으로 처리.
    # commit 중 StaleDataError(동시 수정 충돌) 발생 시 세션 상태를 정리(rollback)한 뒤
    # 예외를 호출자에게 그대로 전달한다. 자동 재시도는 하지 않는다(DEC-007 재시도 안내 방식).
    try:
        db.commit()
    except StaleDataError:
        db.rollback()
        raise

    return request


def get_request(db: Session, request_id: int) -> Request | None:
    """상세 조회 (존재하지 않으면 None)"""
    return db.get(Request, request_id)


def list_requests(
    db: Session,
    pickup_date_from: date | None = None,
    pickup_date_to: date | None = None,
    business_office_id: int | None = None,
    current_status: RequestStatus | None = None,
) -> list[Request]:
    """목록 조회.

    - 기간 필터는 pickup_date(수거희망일) 기준: from <= pickup_date <= to
    - 입력된 조건은 AND로 결합
    - 정렬: pickup_date ASC, id ASC
    - from > to 검증은 호출부(API)가 422/400으로 거부
    """
    stmt = select(Request)
    if pickup_date_from is not None:
        stmt = stmt.where(Request.pickup_date >= pickup_date_from)
    if pickup_date_to is not None:
        stmt = stmt.where(Request.pickup_date <= pickup_date_to)
    if business_office_id is not None:
        stmt = stmt.where(Request.business_office_id == business_office_id)
    if current_status is not None:
        stmt = stmt.where(Request.current_status == current_status)
    stmt = stmt.order_by(Request.pickup_date.asc(), Request.id.asc())
    return db.execute(stmt).scalars().all()


def get_statistics_summary(
    db: Session,
    pickup_date_from: date | None = None,
    pickup_date_to: date | None = None,
    business_office_id: int | None = None,
    current_status: RequestStatus | None = None,
) -> dict:
    """통계 집계 (WP-10).

    목록 API와 동일한 행 집합을 보장하기 위해 list_requests()를 그대로
    재사용해 필터를 적용한 뒤, 결과 행을 메모리에서 집계한다.
    (별도의 집계 쿼리/임의 집계 없음)

    반환 구조:
      - total_requests: 대상 건수
      - by_business_office: {사업소 id(문자열): 건수} — 실제 존재하는 사업소만
      - by_status: 네 상태 키 항상 포함 (0건이어도)
      - quantities: {electric_bed, wheelchair, other_small, total}
    """
    rows = list_requests(
        db,
        pickup_date_from=pickup_date_from,
        pickup_date_to=pickup_date_to,
        business_office_id=business_office_id,
        current_status=current_status,
    )

    by_business_office: dict[str, int] = {}
    by_status: dict[str, int] = {status.value: 0 for status in RequestStatus}
    quantities = {
        "electric_bed": 0,
        "wheelchair": 0,
        "other_small": 0,
        "total": 0,
    }

    for req in rows:
        by_business_office[str(req.business_office_id)] = (
            by_business_office.get(str(req.business_office_id), 0) + 1
        )
        by_status[req.current_status.value] = by_status.get(req.current_status.value, 0) + 1
        quantities["electric_bed"] += req.electric_bed_quantity
        quantities["wheelchair"] += req.wheelchair_quantity
        quantities["other_small"] += req.other_small_quantity

    quantities["total"] = (
        quantities["electric_bed"] + quantities["wheelchair"] + quantities["other_small"]
    )

    return {
        "total_requests": len(rows),
        "by_business_office": by_business_office,
        "by_status": by_status,
        "quantities": quantities,
    }
