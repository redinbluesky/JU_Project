# WP-14-D 지시서 — 최종 quality-gate 재검증 및 출시 판정

담당: `quality-gate`
수정 허용 경로: `docs/40-quality/테스트-결과.md`, `docs/40-quality/결함-목록.md`만.
구현 코드 수정·Git 커밋 금지.

## 현재 기준

- 전체 pytest: `190 passed, 4 warnings`
- Wanted CSS 토큰: 원본과 byte 동일, `4f34aaf`
- 접수폼: `/requests/new`
- 목록: `/admin/requests`
- 상세: `/admin/requests/{id}`
- 통계: `/admin/dashboard`
- 사용자 인수 테스트 PPT: `runtime/사용자-인수-테스트-가이드-Wanted-v1.0.pptx`
- PPT 템플릿: `docs/30-delivery/templates/사용자-인수-테스트-가이드-Wanted-템플릿.pptx`

## 실행

실제 실행:
```
uv run pytest tests/ -v
```

## 검증 범위

이전 WP-13-A/B 문서를 전부 처음부터 다시 읽지 말고, 기존 판정에 다음 신규 결과를 반영해라.

1. UI 자동화 테스트:
   - `tests/test_ui_form.py`: 21개
   - `tests/test_ui_list.py`: 22개
   - `tests/test_ui_detail.py`: 13개
   - `tests/test_ui_dashboard.py`: 7개
2. 실제 브라우저 검증 결과:
   - PC Chrome 기준 `/requests/new`, `/admin/requests`, `/admin/requests/1`, `/admin/dashboard` 모두 200
   - Wanted CSS/앱 CSS/JS와 토큰 정적 자산 200
   - 각 화면 role=status 및 aria-live=polite 확인
   - 모바일 375px에서 네 화면 모두 clientWidth=375, scrollWidth=375, 가로 overflow 없음
   - 상태 텍스트·badge, 상세 이력·버튼, 통계 항목 확인
   - favicon.ico 404는 비차단 관측으로 유지
3. 사용자 테스트 PPT:
   - `runtime/사용자-인수-테스트-가이드-Wanted-v1.0.pptx`
   - 17슬라이드, 190개 테스트 수, 현재 조건부 가능 판정, 참조 노트·부록 포함
   - 템플릿 기반이며 실제 사용자 테스트 결과를 기록하기 위한 문서임을 구분

## 판정

- QA-033~037 및 화면 관련 조건부/미검증 항목을 실제 UI·브라우저 증거로 갱신하라.
- UI가 구현된 것과 사용자가 아직 실제 인수 테스트를 수행하지 않은 것은 구분하라.
- 사용자 수동 테스트가 완료되지 않았다면 최종 판정은 `조건부 가능`으로 유지할지, 자동화·브라우저 검증까지 완료된 상태를 `출시 가능`으로 볼지 근거를 명시하라.
- 기존 500 예외 메시지 노출 관측은 WP-14-A에서 수정됐으므로 결함 목록에서 Fixed/Verified로 갱신하라. 전용 테스트 `tests/test_error_responses.py` 6개, 전체 회귀 190개 근거를 기록하라.
- 확인된 기능 결함과 잔여 위험을 분리하라.

## 산출물

`docs/40-quality/테스트-결과.md`:
- 최종 pytest 결과
- UI 테스트 파일별 통과 수
- PC/mobile 브라우저 증거
- PPT 산출물·참조 일치
- QA-001~040 최종 판정표
- 최종 출시 판정

`docs/40-quality/결함-목록.md`:
- 500 예외 메시지 노출 항목 상태 갱신
- favicon 404·deprecation·runtime 잔여 산출물 등 비차단 위험 기록
- UI/브라우저 검증이 해결된 근거 기록

## 완료 보고

```
WP-14-D 완료
- pytest:
- UI/브라우저:
- PPT:
- QA 판정 변경:
- 확인된 결함:
- 잔여 위험:
- 최종 판정:
- 사용자 결정 필요사항:
```
