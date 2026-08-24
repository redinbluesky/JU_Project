# Wanted Design System 프로젝트 적용 제안

- 작성자: `delivery-lead`
- 상태: 제안 저장 — 구현 전
- 원본 위치: `D:\Tmp\Wanted Design System`
- 대상 프로젝트: `D:\llm\JU_Project`

## 결론

현재 프로젝트는 FastAPI + Jinja2 + Vanilla JS 구조이므로 Wanted Design System의 React JSX 컴포넌트와 `_ds_bundle.js`를 직접 도입하지 않는다. 대신 CSS 토큰·폰트·아이콘·컴포넌트 시각 규칙을 프로젝트의 Jinja-native HTML/CSS 컴포넌트로 재구성한다.

## 적용 원칙

1. `D:\Tmp`를 런타임 참조 경로로 사용하지 않고 필요한 자산만 프로젝트에 복사한다.
2. Wanted 브랜드 로고·채용 플랫폼 전용 콘텐츠·회사/학교 로고는 라이선스 확인 전 사용하지 않는다.
3. `tokens/colors.css`, `typography.css`, `layout.css`, `fonts.css`, `base.css`를 우선 참조한다.
4. React 컴포넌트는 직접 사용하지 않고 Jinja 템플릿과 Vanilla JS로 재작성한다.
5. 기존 API 경로와 pytest 테스트를 변경하지 않는다.
6. 화면은 정보 밀도와 업무 속도를 우선하는 `Operate / Inspect` 표면으로 구성한다.

## 권장 프로젝트 구조

```text
app/
├─ static/
│  ├─ css/
│  │  ├─ wanted-tokens.css
│  │  ├─ wanted-typography.css
│  │  ├─ wanted-components.css
│  │  └─ app.css
│  ├─ js/app.js
│  ├─ fonts/
│  └─ icons/
└─ templates/
   ├─ base.html
   ├─ requests/new.html
   ├─ requests/list.html
   ├─ requests/detail.html
   └─ dashboard/index.html
```

## 우선 적용 토큰

- Primary: `#0066FF`
- 성공: `#00BF40`
- 오류: `#FF4242`
- 경고: `#FF9E00`
- 기본 폰트: Pretendard JP / Pretendard
- 4px 기반 spacing
- 페이지 여백: 20px
- 카드·입력 필드 radius: 12px
- border-first inset ring
- `role="status"`, `aria-live="polite"`

## 화면별 적용

### 접수폼

- 사업소·날짜·장소·주소·수량 입력
- 명시적 label
- Wanted Textfield/Select/Button 시각 규칙
- 입력 오류·성공 메시지
- 모바일 1열 배치

### 목록

- 기간·사업소·상태 필터
- 접수번호·사업소·수거희망일·상태·수량
- 상태 chip/badge는 색상과 텍스트를 함께 사용
- 엑셀 다운로드 버튼
- 모바일에서는 responsive list/card로 전환

### 상세

- 접수번호·현재 상태·주요 정보
- 품목별 수량
- 상태 변경 버튼
- 상태 이력
- PDF 다운로드 버튼
- 모바일 세로 흐름

### 통계

- 장식적 dashboard보다 정보 중심 Monitor 화면으로 구성
- 기간 필터
- 기간·사업소·상태·품목 집계
- 숫자만 과도하게 키우지 않음

## 실행 순서

1. 디자인시스템 라이선스와 자산 범위 확인
2. CSS 토큰·폰트·일반 아이콘을 프로젝트에 복사
3. Jinja `base.html`과 공통 CSS 작성
4. 접수폼 구현
5. 목록·상세 구현
6. 통계 화면 구현
7. UI 테스트 추가
8. PC Chrome 검증
9. 모바일 375px 검증
10. quality-gate 재검증

## 주의

Wanted 커뮤니티 Figma 파일에서 추출된 자산이므로 상업적 사용 시 라이선스를 먼저 확인한다. 라이선스가 불명확하면 토큰과 일반적인 UI 원칙만 사용하고 Wanted 고유 로고·브랜드 자산은 제외한다.
