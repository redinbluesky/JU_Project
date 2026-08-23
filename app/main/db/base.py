from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.types import TypeDecorator, DateTime
from datetime import datetime, timezone


class UTCDateTime(TypeDecorator):
    """timezone-aware UTC datetime만 허용. DB에는 UTC naive로 저장하고
    조회 시 tzinfo=UTC를 다시 붙여 반환한다."""
    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("UTCDateTime 컬럼에는 timezone-aware datetime만 저장할 수 있다")
        return value.astimezone(timezone.utc).replace(tzinfo=None)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return value.replace(tzinfo=timezone.utc)


class Base(DeclarativeBase):
    pass
