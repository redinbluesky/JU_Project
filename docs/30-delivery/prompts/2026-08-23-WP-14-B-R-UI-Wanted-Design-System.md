# WP-14-B-R 재지시서 — Wanted Design System 기반 Jinja UI 1차

담당: `local-builder`
수정 허용 경로: `app/server.py`, `app/templates/`, `app/static/`, `tests/test_ui_pages.py`

## 배경

WP-13 quality-gate의 최종 판정은 UI 미구현으로 인한 **조건부 가능**이었다. Product Owner가 Wanted Design System 적용 제안을 승인했고, 다음 원본을 제공했다.

```text
D:\Tmp\Wanted Design System
```

프로젝트는 FastAPI + Jinja2 + Vanilla JS 구조다. UI 구현은 이 기술 스택을 유지한다.

## 디자인시스템 적용 원칙

1. 원본 `D:\Tmp\Wanted Design System`의 CSS 토큰과 시각 언어를 사용한다.
2. React JSX 컴포넌트, `_ds_bundle.js`, Babel, React CDN을 프로젝트 런타임에 직접 연결하지 마라.
3. Jinja-native HTML/CSS 컴포넌트로 재구성하라.
4. 필요한 CSS 토큰·폰트·일반 아이콘만 `app/static/`으로 복사한다. 원본 D:\Tmp 경로를 런타임에 참조하지 마라.
5. Wanted 고유 로고·채용 플랫폼 콘텐츠·회사/학교 로고는 사용하지 마라. 라이선스 확인 전 브랜드 자산을 복사하지 마라.
6. 기존 `/api/**` 라우터와 127개 이상 테스트를 깨뜨리지 마라.

## 우선 적용 토큰

원본에서 다음을 읽고 프로젝트 CSS로 옮겨라:

- `styles.css`
- `tokens/colors.css`
- `tokens/typography.css`
- `tokens/layout.css`
- `tokens/fonts.css`
- `tokens/base.css`

핵심 시각 규칙:
- Primary `#0066FF`
- 성공 `#00BF40`, 오류 `#FF4242`, 경고 `#FF9E00`
- Pretendard 계열 폰트
- 4px 기반 spacing, 기본 page margin 20px
- 카드/입력 radius 12px
- border-first inset ring
- 과도한 gradient/glassmorphism 금지
- 상태는 색상과 텍스트를 함께 표시

## 화면 경로

- `GET /requests/new` — 접수폼
- `GET /admin/requests` — 목록·필터
- `GET /admin/requests/{id}` — 상세

## 화면 필수 요소

### 공통

- `base.html`
- viewport meta
- 공통 Wanted 토큰 CSS
- 반응형 container
- 메시지 영역:
  ```html
  <div id="live-status" role="status" aria-live="polite"></div>
  ```

### 접수폼

- 사업소 선택
- 수거 희망일
- 수거 장소 유형
- 주소
- 전동침대·휠체어·기타 수량
- 접수 생성 버튼
- 모든 input에 명시적 label
- 기존 `POST /api/requests` 호출
- API 422 오류를 필드/메시지 영역에 표시

### 목록

- 기간·사업소·상태 필터
- 접수번호·사업소·수거 희망일·상태·전체 수량
- 상세 링크
- 엑셀 다운로드
- 기존 `/api/requests` 호출
- 상태는 텍스트와 시각적 badge/chip 병기

### 상세

- 전체 접수 정보
- 현재 상태와 상태 이력
- 상태 변경 버튼
- `DISINFECTED` 이후 PDF 다운로드 버튼
- 기존 status/PATCH/PDF API 호출
- 성공/실패 메시지를 `role=status`, `aria-live=polite`로 표시

## 반응형/접근성

- PC Chrome 기준 1200px 이상 레이아웃
- 모바일 375px에서 가로 스크롤 없이 접수 핵심 흐름 제공
- 터치 대상 최소 44px
- label-for 연결
- 키보드 focus 표시
- 상태를 색상만으로 표현하지 않음
- 오류/성공 메시지에 텍스트 포함

## 테스트

`tests/test_ui_pages.py`를 신규 작성하라. 기존 테스트 파일은 수정하지 마라.

최소 검증:
1. 세 화면 GET 200
2. HTML 주요 label/input/table/status 텍스트 확인
3. `role="status"`, `aria-live="polite"` 확인
4. CSS 토큰 또는 Wanted Primary 색상 사용 확인
5. `/admin/requests` 필터 링크/폼 확인
6. 상세 화면 상태/PDF 버튼 조건 확인
7. 기존 API 회귀

## 실행 명령

```
uv run pytest tests/test_ui_pages.py -v
uv run pytest tests/ -q
```

## 완료 보고

```
WP-14-B-R 완료
- 디자인시스템 복사/적용 경로:
- 생성한 템플릿:
- 생성한 CSS/JS:
- 화면 경로:
- 접근성 요소:
- 반응형 검증:
- 전용 테스트:
- 전체 회귀:
```

실제 HTML/Jinja/CSS 파일을 작성하고 테스트를 실행하기 전에는 완료라고 보고하지 마라.
