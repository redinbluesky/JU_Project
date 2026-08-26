"""WP-15-A — 승인된 반응형 레이아웃 기준 검증."""

from pathlib import Path


def _read(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def test_common_navigation_exposes_hamburger_for_mobile_and_tablet():
    html = _read("app/templates/base.html")
    assert 'id="nav-toggle"' in html
    assert 'aria-controls="app-nav"' in html
    assert 'aria-expanded="false"' in html
    assert 'id="app-nav"' in html
    assert 'href="/admin/dashboard"' in html
    assert 'href="/admin/requests"' in html
    assert 'href="/requests/new"' in html


def test_responsive_breakpoints_match_dec_008_and_dec_008a():
    css = _read("app/static/css/app.css")
    assert "@media (max-width: 767px)" in css
    assert "@media (min-width: 768px) and (max-width: 959px)" in css
    assert "@media (min-width: 960px) and (max-width: 1279px)" in css
    assert "@media (min-width: 1280px)" in css
    assert ".detail-status-action" in css
    assert "position: fixed" in css


def test_mobile_and_narrow_tablet_use_card_list_without_horizontal_scroll():
    css = _read("app/static/css/app.css")
    assert "@media (max-width: 959px)" in css
    assert ".req-table thead" in css
    assert ".req-table td::before" in css
    assert "overflow-x: hidden" in css


def test_request_buttons_are_not_fixed_and_have_responsive_alignment():
    css = _read("app/static/css/app.css")
    assert ".form-actions .btn-primary" in css
    assert "width: 100%" in css
    assert ".form-actions" in css
    assert "justify-content: flex-end" in css


def test_hamburger_script_toggles_menu_and_accessible_state():
    js = _read("app/static/js/app.js")
    assert 'document.getElementById("nav-toggle")' in js
    assert 'getAttribute("aria-expanded")' in js
    assert 'setAttribute("aria-expanded", String(!expanded))' in js
    assert 'classList.toggle("is-open", !expanded)' in js
