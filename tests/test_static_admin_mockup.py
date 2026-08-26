"""관리자 정적 목업의 화면 전환·필터·상태별 PDF 회귀 검증."""
from pathlib import Path


HTML = Path("docs/20-design/admin-login.html").read_text(encoding="utf-8")


def test_admin_mockup_contains_login_list_detail_dashboard_views():
    for view_id in ("admin-login-view", "admin-list-view", "admin-detail-view", "admin-dashboard-view"):
        assert f'id="{view_id}"' in HTML
    for label in ("접수 목록", "접수 상세", "통계 대시보드"):
        assert label in HTML


def test_admin_mockup_has_explicit_filters_and_mobile_layout():
    for field in ("pickup-date-from", "pickup-date-to", "office-filter", "status-filter"):
        assert f'id="{field}"' in HTML
    assert "@media (max-width: 959px)" in HTML
    assert "aria-label=\"목록 필터\"" in HTML


def test_admin_mockup_has_state_change_and_conditional_pdf():
    assert "상태 변경" in HTML
    assert "PDF 다운로드" in HTML
    assert "can-download-pdf" in HTML
    assert "function showAdminView" in HTML
    assert "adminDetailPdf.hidden" in HTML


def test_admin_filter_filters_rows_and_reports_empty_results():
    assert "data-pickup-date" in HTML
    assert "data-office" in HTML
    assert "data-status" in HTML
    assert "admin-filter-row" in HTML
    assert "visibleRows" in HTML
    assert "검색 결과가 없습니다" in HTML


def test_admin_filter_controls_and_result_table_use_full_width_bordered_layout():
    assert '>조회<' in HTML
    assert 'class="admin-result-table"' in HTML
    assert 'class="admin-filter-controls"' in HTML
    css = HTML.split("</style>", 1)[0]
    assert ".admin-filter-controls" in css
    assert "height:44px" in css
    assert ".admin-result-table th,.admin-result-table td" in css
    assert "border:1px solid" in css


def test_admin_detail_has_driver_five_stage_status_and_read_only_timeline():
    for label in ("픽업 담당 기사", "기사명 + 연락처", "접수대기", "수거예정", "입고/소독중", "소독완료", "배송완료"):
        assert label in HTML
    assert "status-timeline" in HTML
    assert "처리 내역 메모" in HTML
    assert "readonly" in HTML


def test_admin_status_transition_has_five_steps_and_pdf_only_from_disinfected():
    assert 'ADMIN_STATUS_STEPS = ["접수대기", "수거예정", "입고/소독중", "소독완료", "배송완료"]' in HTML
    assert "adminStatusIndex + 1" in HTML
    assert "adminStatusIndex < 3" in HTML
    assert "adminDetailPdf.hidden = adminStatusIndex < 3" in HTML
    assert "adminDetailPdf.hidden = false" not in HTML


def test_admin_detail_spacing_and_full_width_controls():
    css = HTML.split("</style>", 1)[0]
    assert ".detail-status-row" in css and "justify-content:space-between" in css
    assert ".detail-status-row > .status-pill" in css and "margin-left:var(--space-4)" in css
    assert ".driver-assignment" in css and "font-size:inherit" in css
    assert ".driver-assignment" in css and "gap:var(--space-4)" in css
    assert ".admin-process-memo" in css and "width:100%" in css


def test_pages_public_assets_and_admin_demo_warning_are_declared():
    assert 'src="assets/gwangju-welfare-disinfection-banner-pc.png"' in HTML
    assert "정적 데모" in HTML
    assert "실제 인증·권한을 제공하지 않음" in HTML
    workflow = Path(".github/workflows/pages.yml").read_text(encoding="utf-8")
    assert "docs/20-design/admin-login.html" in workflow
    assert "docs/20-design/pc-applicant-info.html" in workflow
    assert "actions/deploy-pages" in workflow


def test_admin_banner_matches_wide_content_container():
    css = HTML.split("</style>", 1)[0]
    assert ".site-banner" in css
    assert ".site-banner,.admin-card--wide" in css
    assert "max-width:960px" in css
    assert "margin:0 auto" in css


def test_guide_menu_switches_right_panel_with_placeholder_copy():
    html = Path("docs/20-design/pc-applicant-info.html").read_text(encoding="utf-8")
    for key, label in (("howto", "이용 방법"), ("process", "처리 절차"), ("pickup-prep", "수거 준비사항")):
        assert f'data-guide="{key}"' in html
        assert label in html
    assert 'id="guide-panel-title"' in html
    assert 'id="guide-panel-message"' in html
    assert "내용은 추후 추가 예정입니다." in html
    assert "guide-link" in html
    assert "guidePanelTitle.textContent" in html


def test_guide_mode_replaces_entire_right_content_and_new_application_restores_it():
    html = Path("docs/20-design/pc-applicant-info.html").read_text(encoding="utf-8")
    css = html.split("</style>", 1)[0]
    assert "body.guide-mode #applicant-card" in css
    assert "body.guide-mode #lookup-detail" in css
    assert "body.guide-mode .body-layout" in css
    assert "body.guide-mode .guide-panel" in css
    assert "document.body.classList.add(\"guide-mode\")" in html
    assert "document.body.classList.remove(\"guide-mode\")" in html


def test_new_application_has_no_pickup_prep_section_and_guide_panel_is_first_right_section():
    html = Path("docs/20-design/pc-applicant-info.html").read_text(encoding="utf-8")
    assert 'id="guide-pickup-prep"' not in html
    assert html.index('id="guide-panel"') < html.index('id="applicant-card"')


def test_pickup_prep_selection_targets_top_guide_panel_and_hides_other_content():
    html = Path("docs/20-design/pc-applicant-info.html").read_text(encoding="utf-8")
    assert 'data-guide="pickup-prep" href="#guide-panel"' in html
    assert 'id="guide-panel"' in html
    assert 'guidePanelTitle.textContent = link.textContent' in html
    assert html.index('id="guide-panel"') < html.index('id="applicant-card"')


def test_lookup_mode_keeps_kakao_notification_option_visible():
    html = Path("docs/20-design/pc-applicant-info.html").read_text(encoding="utf-8")
    assert 'id="kakao-notify"' in html
    assert "카카오톡 알림 받기" in html
    assert "접수·수거·처리 상태를 카카오톡으로 안내받습니다." in html
    css = html.split("</style>", 1)[0]
    assert "body.lookup-mode .kakao-opt" not in css
