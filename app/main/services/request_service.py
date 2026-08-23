"""Request 생성 서비스"""

from sqlalchemy.orm import Session
from datetime import datetime, timezone
from app.main.models.models import Request, RequestStatus, RequestStatusHistory, PickupLocationType
from app.main.schemas.request import RequestCreate


def create_request(db: Session, data: RequestCreate) -> Request:
    """Request 생성 - 임시 채번 방식 (R-{순번})"""
    now = datetime.now(timezone.utc)
    
    # 임시 채번: 현재 접수 건수 + 1
    count = db.query(Request).count()
    request_no = f"R-{count + 1:010d}"
    
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
