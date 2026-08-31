# Google Sheets 데모 저장 연동

이 디렉터리의 `Code.gs`를 사용자 계정의 대상 Google Sheet에서 **확장 프로그램 → Apps Script**로 복사합니다.

1. 시트에 `접수 데이터` 탭을 만들거나 Apps Script가 자동 생성하도록 둡니다.
2. `Code.gs`를 붙여넣고 저장합니다.
3. **배포 → 새 배포 → 웹 앱**으로 배포합니다.
4. 발급된 웹 앱 URL을 공개 HTML의 `GOOGLE_SHEETS_WEB_APP_URL`에 직접 입력하지 말고, 테스트용 로컬 사본에서만 설정합니다. 공개 GitHub Pages에는 빈 문자열을 유지합니다.
5. 가상 데이터로 정상 저장·동일 `request_id` 재전송·잘못된 payload 거부를 확인합니다.

이 연동은 `DEMO_ONLY`가 true인 쓰기 전용 데모입니다. 이름·전화번호·주소는 서버에서 가상 값으로 치환하며 조회·수정 API를 제공하지 않습니다. 실제 개인정보 저장에는 공개 HTML/App Script 직접 호출을 사용하지 말고 인증된 자체 백엔드와 Sheets API OAuth를 사용해야 합니다.
