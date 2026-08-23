# DEV-002 실행 지시서 (2/6) — SQLAlchemy 모델 + DB 엔진/세션 코드

담당: `local-builder` | 대상: `app/main/db/`, `app/main/models/`

## 배경

1/6(프로젝트 셋업) 완료 확인됨 — `.venv` 생성, 모든 의존성 설치 성공. 이번엔 **2단계, SQLAlchemy 코드만** 작성한다. 짧게 끝내라.

## 읽을 문서

`docs/20-design/데이터-모델.md` (전체, 특히 2절 테이블정의 / 4절 낙관적잠금 / 5절 시간저장 / 6절 Enum / 8절 SQLAlchemy모델매핑)

## 작업 (파일 3개만 작성)

1. `app/main/db/base.py` — SQLAlchemy `Base` 선언, `UTCDateTime` TypeDecorator (데이터-모델.md 5절 코드 그대로)
2. `app/main/db/session.py` — engine, SessionLocal, PRAGMA foreign_keys/journal_mode 설정 (데이터-모델.md 13절 참고. DB 경로는 `runtime/db/ju-project.db`)
3. `app/main/models/models.py` — BusinessOffice, Request, RequestStatusHistory, RequestNoCounter, RequestStatus(enum), PickupLocationType(enum) — 데이터-모델.md 8절 기준

작성 후 실제로 import 되는지 검증하라:
```
uv run python -c "from app.main.models.models import Request, BusinessOffice, RequestStatusHistory, RequestNoCounter; from app.main.db.session import engine; print('OK')"
```

## 완료 보고 형식

```
2/6 완료
- 작성 파일: (경로 3개, 각 verified 여부)
- import 검증 명령 실행 결과: (실제 출력, exit code)
```

실제 `uv run` 명령을 실행하지 않고 보고하면 승인하지 않는다.
