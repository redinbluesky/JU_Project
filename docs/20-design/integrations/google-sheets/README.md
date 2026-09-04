# Google Sheets 데모 저장 연동

이 디렉터리의 `Code.gs`를 사용자 계정의 대상 Google Sheet에서 **확장 프로그램 → Apps Script**로 복사합니다.

1. 시트에 `접수 데이터` 탭을 만들거나 Apps Script가 자동 생성하도록 둡니다.
2. `Code.gs`를 붙여넣고 저장합니다.
3. **배포 → 새 배포 → 웹 앱**으로 배포합니다.
4. 발급된 웹 앱 URL을 공개 HTML의 `GOOGLE_SHEETS_WEB_APP_URL`에 설정합니다. 이 URL은 공개 엔드포인트이므로 가상 데이터만 사용합니다.
5. 가상 데이터로 정상 저장·동일 `request_id` 재전송·잘못된 payload 거부를 확인합니다.
6. 관리자 목업의 `admin-login.html`에서 데모 로그인 후 신청번호와 휴대전화로 저장 데이터를 조회합니다. 조회는 두 값을 모두 알아야 하며, `demo=true`가 없는 요청과 형식 오류는 거부됩니다.

이 연동은 `DEMO_ONLY`가 true인 쓰기 전용 데모입니다. 이름·전화번호·주소는 제출 payload의 값을 수식 주입 방어 후 그대로 저장하므로 반드시 가상값만 입력해야 하며, 조회·수정 API를 제공하지 않습니다. 실제 개인정보 저장에는 공개 HTML/App Script 직접 호출을 사용하지 말고 인증된 자체 백엔드와 Sheets API OAuth를 사용해야 합니다.
