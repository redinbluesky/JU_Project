"""신규 접수 입력 오류가 눈에 띄는 접근성 알림으로 제공되는지 검증."""

from pathlib import Path


def _read(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def test_new_request_page_has_dismissible_error_alert_container():
    html = _read("app/templates/base.html")
    assert 'id="error-alert"' in html
    assert 'role="alert"' in html
    assert 'aria-live="assertive"' in html
    assert 'type="button"' in html
    assert 'aria-label="알림 닫기"' in html


def test_error_alert_is_prominently_positioned_and_keyboard_focusable():
    css = _read("app/static/css/app.css")
    assert "#error-alert" in css
    assert "position: fixed" in css
    assert "z-index" in css
    assert "#error-alert:focus" in css or "#error-alert:focus-visible" in css


def test_request_errors_are_translated_to_plain_korean_and_shown_in_alert():
    js = _read("app/static/js/app.js")
    assert "function showErrorAlert" in js
    assert "품목 수량을 하나 이상 입력해 주세요." in js
    assert "필수 입력값을 확인해 주세요." in js
    assert "수거 희망일은 오늘 이후 날짜로 선택해 주세요." in js
    assert "수거 희망일을 확인해 주세요." in js
    assert "수량은 0 이상으로 입력해 주세요." in js
    assert "showErrorAlert" in js
    assert "hideErrorAlert" in js


def test_request_error_alert_can_be_closed_with_escape():
    js = _read("app/static/js/app.js")
    assert "keydown" in js
    assert 'event.key === "Escape"' in js or "event.key === 'Escape'" in js
    assert "hideErrorAlert" in js


def test_success_redirect_is_preserved_without_success_alert():
    js = _read("app/static/js/app.js")
    assert 'window.location.assign("/requests/complete/" + data.id)' in js
    assert "showErrorAlert(\"접수가 완료" not in js
