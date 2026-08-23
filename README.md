# JU Project

광주·전남 복지용구 위탁소독 업무의 접수·상태·이력 관리 시스템 프로젝트다.

## 현재 단계

4~6주 내 로컬 환경에서 기술 흐름 프로토타입을 완성한다.

```text
접수 → 수거완료 → 소독완료 → 배송완료
```

## 기준 문서

- 1단계 범위와 인수 조건: `docs/10-scope/1단계-기술-프로토타입-목표-범위-인수조건.md`
- 원본 요구사항: `docs/00-input/원본-요구사항-RFP.md`
- BOT 운영 방식: `docs/30-delivery/Hermes-BOT-팀-구성안.md`

## 폴더

- `docs/00-input`: 최초 입력과 원본 요구사항
- `docs/10-scope`: 승인된 범위와 인수 조건
- `docs/20-design`: UX·시스템·데이터 설계
- `docs/30-delivery`: 계획·결정·진행 관리
  - `docs/30-delivery/prompts`: BOT에 실제 전달한 주요 프롬프트 이력
- `docs/40-quality`: 인수 검증·테스트·결함
- `app`: 애플리케이션 단일 소스
- `runtime`: 로컬 DB·엑셀·PDF 생성물(Git 제외)

기술 스택이 확정될 때까지 `app` 내부 구조는 만들지 않는다.
